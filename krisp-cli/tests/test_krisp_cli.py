"""Regression tests for krisp_cli.py.

Run with pytest; the nix build runs them via pytestCheckHook. Bare test
functions, so `unittest discover` collects nothing. Plain asserts and stdlib
only — matching atlassian-cli/tests, and keeping pytest out of the treefmt
mypy env.

atlassian_cli.py is a fork of this file and carries the same tests. The two
drift-copy each other, so a defect fixed in one is worth pinning in both —
that shared lineage is how the unguarded discovery call reached both.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import time
from pathlib import Path
from typing import Any, ClassVar, Self

import click
import httpx

SRC = Path(__file__).resolve().parent.parent / "krisp_cli.py"
_spec = importlib.util.spec_from_file_location("krisp_cli_under_test", SRC)
assert _spec and _spec.loader
kc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kc)


class _UnreachableClient:
    """httpx.Client stand-in whose every request fails as if the host is down."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise httpx.ConnectError("network is down")

    def post(self, *args: Any, **kwargs: Any) -> Any:
        raise httpx.ConnectError("network is down")


def test_refresh_token_names_the_endpoint_when_discovery_is_unreachable():
    """An unreachable metadata host is not a spent grant. Answering None sends
    the caller to _get_token's "Run: krisp-cli auth", and `auth` opens with
    this same request - so the outage has to name the endpoint that went dark
    instead of impersonating expired credentials."""
    with tempfile.TemporaryDirectory() as td:
        client_path = Path(td) / "client.json"
        client_path.write_text(json.dumps({"client_id": "test-client"}))
        orig_client_path, orig_client = kc.CLIENT_PATH, kc.httpx.Client
        kc.CLIENT_PATH = client_path
        kc.httpx.Client = _UnreachableClient
        try:
            kc._refresh_token({"refresh_token": "stale-token"})
        except click.ClickException as exc:
            base = kc.MCP_URL.rsplit("/mcp", 1)[0]
            assert f"{base}/.well-known/oauth-protected-resource" in str(exc)
        else:
            raise AssertionError("an unreachable discovery host must raise")
        finally:
            kc.CLIENT_PATH = orig_client_path
            kc.httpx.Client = orig_client


def test_refresh_token_returns_none_when_the_grant_is_declined():
    """The other side of the split above: endpoints that answer fine and a
    token endpoint that refuses the refresh token IS the spent-grant case, and
    it still has to reach the re-auth prompt as None."""
    with tempfile.TemporaryDirectory() as td:
        client_path = Path(td) / "client.json"
        client_path.write_text(json.dumps({"client_id": "test-client"}))
        orig = (kc.CLIENT_PATH, kc._discover_oauth, kc._exchange_token)
        kc.CLIENT_PATH = client_path
        kc._discover_oauth = lambda: {"token_endpoint": "https://example.invalid/token"}
        kc._exchange_token = lambda meta, data: {"error": "invalid_grant"}
        try:
            assert kc._refresh_token({"refresh_token": "stale-token"}) is None
        finally:
            kc.CLIENT_PATH, kc._discover_oauth, kc._exchange_token = orig


def test_refresh_token_returns_none_without_a_registered_client():
    """No client.json means nothing to refresh with — the early return, kept
    honest so the network test above cannot pass for the wrong reason."""
    with tempfile.TemporaryDirectory() as td:
        orig = kc.CLIENT_PATH
        kc.CLIENT_PATH = Path(td) / "does-not-exist.json"
        try:
            assert kc._refresh_token({"refresh_token": "stale-token"}) is None
        finally:
            kc.CLIENT_PATH = orig


AUTH_SERVER = "https://example.invalid"
TOKEN_ENDPOINT = "https://example.invalid/token"
# Both hops krisp's discovery walks: PRM first, then AS metadata.
DISCOVERY = [{"authorization_servers": [AUTH_SERVER]}, {"token_endpoint": TOKEN_ENDPOINT}]


class _FakeResponse:
    """Enough of httpx.Response for _discover_oauth and _exchange_token."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload)

    def raise_for_status(self) -> None:
        pass

    def json(self) -> Any:
        return self._payload


class _RecordingClient:
    """httpx.Client stand-in replaying canned JSON and logging every request.

    The log is what lets the success path assert the OAuth form and the
    endpoint it was posted to; a fake that answered anything would let a wrong
    endpoint or a malformed form through.
    """

    gets: ClassVar[list[Any]] = []
    post_payload: ClassVar[Any] = {}
    requests: ClassVar[list[tuple[str, str, Any]]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._gets = list(_RecordingClient.gets)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def get(self, url: str, *args: Any, **kwargs: Any) -> Any:
        _RecordingClient.requests.append(("GET", url, None))
        return _FakeResponse(self._gets.pop(0))

    def post(self, url: str, *args: Any, **kwargs: Any) -> Any:
        _RecordingClient.requests.append(("POST", url, kwargs.get("data")))
        return _FakeResponse(_RecordingClient.post_payload)


def _refresh_with(gets, post_payload, unwritable_token=False):
    """Drive _refresh_token against canned HTTP, paths inside a temp dir.

    Returns (result, persisted-token-or-None); the saved file is read before
    the temp dir goes away. Unannotated on purpose, for the reason
    _load_snapshot_from gives in test_validate_skill_doc.py: the module under
    test is loaded by path, so mypy sees a bare ModuleType and rejects every
    attribute on it inside a checked body."""
    _RecordingClient.gets = list(gets)
    _RecordingClient.post_payload = post_payload
    _RecordingClient.requests = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        client_path = root / "client.json"
        client_path.write_text(json.dumps({"client_id": "test-client"}))
        if unwritable_token:
            # A regular file where _save_json needs a directory. Fails for
            # every uid, unlike a chmod, which root would sail through.
            blocked = root / "blocked"
            blocked.write_text("not a directory")
            token_path = blocked / "token.json"
        else:
            token_path = root / "token.json"
        orig = (kc.CLIENT_PATH, kc.TOKEN_PATH, kc.httpx.Client)
        kc.CLIENT_PATH = client_path
        kc.TOKEN_PATH = token_path
        kc.httpx.Client = _RecordingClient
        try:
            result = kc._refresh_token({"refresh_token": "stale-token"})
            saved = json.loads(token_path.read_text()) if token_path.exists() else None
            return result, saved
        finally:
            kc.CLIENT_PATH, kc.TOKEN_PATH, kc.httpx.Client = orig


def _sole_post():
    """The one POST a refresh should have made, as (url, form)."""
    posts = [r for r in _RecordingClient.requests if r[0] == "POST"]
    assert len(posts) == 1, f"expected exactly one POST, got {posts}"
    return posts[0][1], posts[0][2]


def test_refresh_token_success_path():
    """The happy path, absent until now: without it an always-None regression
    passes the whole suite. Asserts the wire too — the POST has to carry the
    OAuth refresh form to the endpoint discovery just handed back."""
    before = time.time()
    got, saved = _refresh_with(
        DISCOVERY,
        {"access_token": "fresh", "expires_in": 3600},
    )
    assert got is not None, "a canned 200 must produce a token"
    assert got["access_token"] == "fresh"
    assert before + 3540 - 5 <= got["expires_at"] <= time.time() + 3540 + 5
    assert saved is not None and saved["access_token"] == "fresh"
    url, form = _sole_post()
    assert url == TOKEN_ENDPOINT, "the POST must go to the discovered endpoint"
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "stale-token"
    assert form["client_id"] == "test-client"


def test_non_numeric_expires_in_records_no_expiry():
    """A server sending garbage for expires_in used to raise TypeError past
    every guard. The token still works, so it is kept without an expiry."""
    got, _ = _refresh_with(
        DISCOVERY,
        {"access_token": "fresh", "expires_in": "soon"},
    )
    assert got is not None and got["access_token"] == "fresh"
    assert "expires_at" not in got


def test_infinite_expires_in_records_no_expiry():
    """float("Infinity") survives the arithmetic, so without a finiteness
    check it is persisted as a token that never expires."""
    got, saved = _refresh_with(
        DISCOVERY,
        {"access_token": "fresh", "expires_in": "Infinity"},
    )
    assert got is not None and "expires_at" not in got
    assert saved is not None and "expires_at" not in saved


def test_expires_in_beyond_float_range_records_no_expiry():
    """An int too large for float raises OverflowError, which is neither a
    TypeError nor a ValueError and so has to be named to be caught."""
    got, _ = _refresh_with(
        DISCOVERY,
        {"access_token": "fresh", "expires_in": 10**400},
    )
    assert got is not None and "expires_at" not in got


def test_scalar_exchange_response_is_rejected():
    """A bare JSON string makes `"access_token" in new_data` a substring test
    that passes, handing _get_token a str it crashes indexing."""
    got, _ = _refresh_with(DISCOVERY, "access_token")
    assert got is None


def test_discovery_naming_no_authorization_server_raises():
    """A reachable server is not a working one. An empty authorization_servers
    list is caught in _discover_oauth and named, rather than surfacing as a
    spent grant the re-auth prompt cannot fix."""
    try:
        _refresh_with([{"authorization_servers": []}], {})
    except click.ClickException as exc:
        assert "no authorization server" in str(exc)
    else:
        raise AssertionError("discovery naming no authorization server must raise")


def test_unpersistable_token_raises():
    """A token that cannot be written is environmental, not a spent grant:
    answering None would send the user to `auth`, which ends in this very
    write. Same split _discover_oauth draws."""
    try:
        _refresh_with(
            DISCOVERY,
            {"access_token": "fresh", "expires_in": 3600},
            unwritable_token=True,
        )
    except click.ClickException as exc:
        assert "could not persist" in str(exc)
    else:
        raise AssertionError("an unwritable token path must raise")
