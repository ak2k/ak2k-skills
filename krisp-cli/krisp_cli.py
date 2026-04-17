"""Krisp MCP CLI — dynamic client for Krisp's MCP server over Streamable HTTP.

Discovers tools at runtime via MCP's tools/list, so it adapts automatically
when Krisp adds or changes tools. Auth is OAuth 2.0 with PKCE.

When Cloudflare blocks programmatic requests to api.krisp.ai, the CLI falls
back to performing registration and token exchange through the user's browser.
"""

import base64
import hashlib
import json
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import parse_qs, urlencode, urlparse

import click
import httpx

MCP_URL = "https://mcp.krisp.ai/mcp"
CONFIG_DIR = Path.home() / ".config" / "krisp"
TOKEN_PATH = CONFIG_DIR / "token.json"
CLIENT_PATH = CONFIG_DIR / "client.json"
REDIRECT_PORT = 19876
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"


# --- Helpers ---


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _pkce() -> tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def _load_json(path: Path) -> dict | None:
    if path.exists():
        return cast(dict, json.loads(path.read_text()))
    return None


def _is_cloudflare_blocked(response: httpx.Response) -> bool:
    """Check if a response is a Cloudflare block page."""
    ct = response.headers.get("content-type", "")
    if "text/html" in ct and response.status_code in (403, 503):
        return "cloudflare" in response.text.lower()
    return False


def _browser_post(
    url: str,
    payload: dict,
    *,
    form: bool = False,
    port: int = REDIRECT_PORT,
) -> dict:
    """POST to a URL via the user's browser to bypass Cloudflare.

    Serves a local HTML page that uses fetch() to POST the payload,
    then redirects the JSON response back to localhost.

    If form=True, sends as application/x-www-form-urlencoded (for OAuth
    token endpoints). Otherwise sends as application/json (for registration).
    """
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/result":
                nonlocal result
                qs = parse_qs(urlparse(self.path).query)
                data = qs.get("data", [None])[0]
                if data:
                    result = json.loads(base64.urlsafe_b64decode(data + "=="))
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Done! You can close this tab.</h1>")
                return

            # Serve the page that does the fetch
            payload_json = json.dumps(payload)
            if form:
                body_expr = f"new URLSearchParams({payload_json}).toString()"
                ct = "application/x-www-form-urlencoded"
            else:
                body_expr = f"JSON.stringify({payload_json})"
                ct = "application/json"
            html = f"""<!DOCTYPE html><html><body>
<p>Completing authentication with Krisp...</p>
<script>
fetch("{url}", {{
  method: "POST",
  headers: {{"Content-Type": "{ct}"}},
  body: {body_expr}
}})
.then(r => r.json())
.then(data => {{
  const encoded = btoa(JSON.stringify(data))
    .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
  window.location = "http://localhost:{port}/result?data=" + encoded;
}})
.catch(err => {{
  document.body.innerHTML = "<h1>Error: " + err.message + "</h1>";
}});
</script></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html.encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", port), Handler)
    webbrowser.open(f"http://localhost:{port}/register")
    server.handle_request()  # serve the HTML page
    server.handle_request()  # receive the result redirect
    server.server_close()
    return result


# --- OAuth ---


def _discover_oauth() -> dict:
    """Discover OAuth endpoints via RFC 9470 + RFC 8414."""
    base = MCP_URL.rsplit("/mcp", 1)[0]
    with httpx.Client() as c:
        r = c.get(f"{base}/.well-known/oauth-protected-resource")
        r.raise_for_status()
        res = r.json()
        if "error" in res:
            raise click.ClickException(f"OAuth discovery failed: {res}")
        auth_server = res["authorization_servers"][0]

        r = c.get(f"{auth_server}/.well-known/oauth-authorization-server")
        r.raise_for_status()
        meta: dict = r.json()
        if "error" in meta:
            raise click.ClickException(f"OAuth discovery failed: {meta}")

        return meta


def _register_client(meta: dict) -> dict | None:
    """Dynamic client registration (RFC 7591).

    Tries a direct POST first; if Cloudflare blocks it, falls back to
    performing the POST through the user's browser.
    """
    reg_endpoint = meta.get("registration_endpoint")
    if not reg_endpoint:
        return None

    reg_payload = {
        "client_name": "krisp-cli",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }

    # Try direct POST
    with httpx.Client() as c:
        try:
            r = c.post(reg_endpoint, json=reg_payload)
            if r.status_code in (200, 201) and not _is_cloudflare_blocked(r):
                data: dict = r.json()
                _save_json(CLIENT_PATH, data)
                return data
        except httpx.HTTPError:
            pass

    # Fall back to browser-based registration
    click.echo("Direct registration blocked, using browser fallback...")
    data = _browser_post(reg_endpoint, reg_payload)
    if data and "client_id" in data:
        _save_json(CLIENT_PATH, data)
        return data
    return None


def _exchange_token(meta: dict, token_data_req: dict) -> dict:
    """Exchange an authorization code for tokens.

    Tries a direct POST first; if Cloudflare blocks it, falls back to
    performing the exchange through the user's browser.
    """
    token_endpoint = meta["token_endpoint"]

    with httpx.Client() as c:
        try:
            r = c.post(token_endpoint, data=token_data_req)
            if r.status_code == 200 and not _is_cloudflare_blocked(r):
                return cast(dict, r.json())
        except httpx.HTTPError:
            pass

    # Fall back to browser-based token exchange
    click.echo("Direct token exchange blocked, using browser fallback...")
    return _browser_post(token_endpoint, token_data_req, form=True)


def _refresh_token(token_data: dict) -> dict | None:
    """Refresh an expired access token."""
    client = _load_json(CLIENT_PATH)
    if not client or not token_data.get("refresh_token"):
        return None
    meta = _discover_oauth()
    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id": client["client_id"],
    }
    if client.get("client_secret"):
        refresh_data["client_secret"] = client["client_secret"]

    try:
        new_data = _exchange_token(meta, refresh_data)
    except Exception:
        return None

    if new_data and "access_token" in new_data:
        if "expires_in" in new_data:
            new_data["expires_at"] = time.time() + new_data["expires_in"] - 60
        _save_json(TOKEN_PATH, new_data)
        return new_data
    return None


def _get_token() -> str:
    """Get a valid access token, refreshing if needed."""
    data = _load_json(TOKEN_PATH)
    if not data:
        click.echo("Not authenticated. Run: krisp-cli auth", err=True)
        raise SystemExit(1)

    if data.get("expires_at", 0) > time.time():
        return cast(str, data["access_token"])

    refreshed = _refresh_token(data)
    if refreshed:
        return cast(str, refreshed["access_token"])

    click.echo("Token expired. Run: krisp-cli auth", err=True)
    raise SystemExit(1)


# --- MCP Client ---


class MCPClient:
    """Minimal MCP client over Streamable HTTP."""

    def __init__(self, url: str, token: str):
        self.url = url
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self.client = httpx.Client(timeout=30)
        self._req_id = 0
        self._initialize()

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _post(self, method: str, params: dict | None = None) -> dict:
        payload: dict = {"jsonrpc": "2.0", "id": self._next_id(), "method": method}
        if params:
            payload["params"] = params

        r = self.client.post(self.url, json=payload, headers=self.headers)
        r.raise_for_status()

        # Capture session ID
        sid = r.headers.get("mcp-session-id")
        if sid:
            self.headers["Mcp-Session-Id"] = sid

        # Handle SSE vs JSON response
        ct = r.headers.get("content-type", "")
        if "text/event-stream" in ct:
            result = None
            for line in r.text.splitlines():
                if line.startswith("data: "):
                    result = json.loads(line[6:])
            if result and "error" in result:
                raise click.ClickException(json.dumps(result["error"]))
            return result.get("result", {}) if result else {}
        else:
            result = r.json()
            if "error" in result:
                raise click.ClickException(json.dumps(result["error"]))
            return cast(dict, result.get("result", {}))

    def _notify(self, method: str) -> None:
        self.client.post(
            self.url,
            json={"jsonrpc": "2.0", "method": method},
            headers=self.headers,
        )

    def _initialize(self) -> None:
        self._post(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "krisp-cli", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized")

    def list_tools(self) -> list[dict]:
        result = self._post("tools/list")
        return cast(list[dict], result.get("tools", []))

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        return self._post("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> None:
        self.client.close()


def _mcp() -> MCPClient:
    return MCPClient(MCP_URL, _get_token())


# --- CLI ---


@click.group()
def main():
    """Krisp MCP CLI — dynamic client for Krisp's MCP server."""


@main.command()
def auth():
    """Authenticate with Krisp via OAuth PKCE."""
    meta = _discover_oauth()

    # Get or register client
    client = _load_json(CLIENT_PATH)
    if not client:
        client = _register_client(meta)
    if not client:
        raise click.ClickException("Client registration failed. Check your network connection.")

    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)

    # Use scopes from client registration, not the full server list
    scopes = client.get("scope", "")
    params = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    if scopes:
        params["scope"] = scopes
    auth_url = meta["authorization_endpoint"] + "?" + urlencode(params)

    # Local server to capture the redirect
    auth_code = None

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            qs = parse_qs(urlparse(self.path).query)
            if qs.get("state", [None])[0] != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch")
                return
            auth_code = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Authenticated! You can close this tab.</h1>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", REDIRECT_PORT), Handler)
    click.echo("Opening browser for authentication...")
    webbrowser.open(auth_url)
    server.handle_request()
    server.server_close()

    if not auth_code:
        raise click.ClickException("Authentication failed — no code received.")

    # Exchange code for token
    token_data_req = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client["client_id"],
        "code_verifier": verifier,
    }
    if client.get("client_secret"):
        token_data_req["client_secret"] = client["client_secret"]

    token_data = _exchange_token(meta, token_data_req)
    if not token_data or "access_token" not in token_data:
        raise click.ClickException("Token exchange failed — no access token received.")

    if "expires_in" in token_data:
        token_data["expires_at"] = time.time() + token_data["expires_in"] - 60
    _save_json(TOKEN_PATH, token_data)

    click.echo("Authenticated successfully. Token cached.")


@main.command()
def tools():
    """List available MCP tools (discovered dynamically)."""
    mcp = _mcp()
    try:
        for tool in mcp.list_tools():
            name = tool["name"]
            desc = tool.get("description", "")
            click.echo(f"  {name:30s} {desc}")
    finally:
        mcp.close()


@main.command()
@click.argument("tool_name")
@click.argument("args_json", default="{}")
def call(tool_name: str, args_json: str):
    """Call an MCP tool by name with JSON arguments.

    Examples:

      krisp-cli call search_meetings '{"search": "standup"}'

      krisp-cli call list_action_items '{"completed": false}'

      krisp-cli call list_upcoming_meetings '{"days": 7}'
    """
    try:
        arguments = json.loads(args_json)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")

    mcp = _mcp()
    try:
        result = mcp.call_tool(tool_name, arguments)
        # Format output: extract text content if present
        if isinstance(result, dict) and "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    # Try to pretty-print if it's JSON
                    try:
                        parsed = json.loads(item["text"])
                        click.echo(json.dumps(parsed, indent=2))
                    except (json.JSONDecodeError, TypeError):
                        click.echo(item["text"])
                else:
                    click.echo(json.dumps(item, indent=2))
        else:
            click.echo(json.dumps(result, indent=2))
    finally:
        mcp.close()


@main.command()
def status():
    """Check authentication status."""
    data = _load_json(TOKEN_PATH)
    if not data:
        click.echo("Not authenticated. Run: krisp-cli auth")
        return
    expires = data.get("expires_at", 0)
    remaining = int(expires - time.time())
    if remaining > 0:
        click.echo(f"Authenticated. Token expires in {remaining // 60}m {remaining % 60}s.")
    else:
        if _refresh_token(data):
            click.echo("Token refreshed successfully.")
        else:
            click.echo("Token expired. Run: krisp-cli auth")


@main.command()
def logout():
    """Remove cached tokens and client registration."""
    removed = False
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        click.echo("Token removed.")
        removed = True
    if CLIENT_PATH.exists():
        CLIENT_PATH.unlink()
        click.echo("Client registration removed.")
        removed = True
    if not removed:
        click.echo("Nothing to remove.")


if __name__ == "__main__":
    main()
