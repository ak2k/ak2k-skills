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
from pathlib import Path
from typing import Any, Self

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
