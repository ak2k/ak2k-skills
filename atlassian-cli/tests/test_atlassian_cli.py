"""Regression tests for atlassian_cli.py.

Run with pytest; the nix build runs them via pytestCheckHook. Bare test
functions, so `unittest discover` collects nothing. Plain asserts and stdlib
only — matching test_validate_skill_doc.py, and keeping pytest out of the
treefmt mypy env.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any, Self

import click
import httpx

SRC = Path(__file__).resolve().parent.parent / "atlassian_cli.py"
_spec = importlib.util.spec_from_file_location("atlassian_cli_under_test", SRC)
assert _spec and _spec.loader
ac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ac)


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
    the caller to _get_token's "Run: atlassian-cli auth", and `auth` opens with
    this same request - so the outage has to name the endpoint that went dark
    instead of impersonating expired credentials."""
    with tempfile.TemporaryDirectory() as td:
        client_path = Path(td) / "client.json"
        client_path.write_text(json.dumps({"client_id": "test-client"}))
        orig_client_path, orig_client = ac.CLIENT_PATH, ac.httpx.Client
        ac.CLIENT_PATH = client_path
        ac.httpx.Client = _UnreachableClient
        try:
            ac._refresh_token({"refresh_token": "stale-token"})
        except click.ClickException as exc:
            assert ac.AS_METADATA_URL in str(exc)
        else:
            raise AssertionError("an unreachable discovery host must raise")
        finally:
            ac.CLIENT_PATH = orig_client_path
            ac.httpx.Client = orig_client


def test_refresh_token_returns_none_when_the_grant_is_declined():
    """The other side of the split above: endpoints that answer fine and a
    token endpoint that refuses the refresh token IS the spent-grant case, and
    it still has to reach the re-auth prompt as None."""
    with tempfile.TemporaryDirectory() as td:
        client_path = Path(td) / "client.json"
        client_path.write_text(json.dumps({"client_id": "test-client"}))
        orig = (ac.CLIENT_PATH, ac._discover_oauth, ac._exchange_token)
        ac.CLIENT_PATH = client_path
        ac._discover_oauth = lambda: {"token_endpoint": "https://example.invalid/token"}
        ac._exchange_token = lambda meta, data: {"error": "invalid_grant"}
        try:
            assert ac._refresh_token({"refresh_token": "stale-token"}) is None
        finally:
            ac.CLIENT_PATH, ac._discover_oauth, ac._exchange_token = orig


def test_refresh_token_returns_none_without_a_registered_client():
    """No client.json means nothing to refresh with — the early return, kept
    honest so the network test above cannot pass for the wrong reason."""
    with tempfile.TemporaryDirectory() as td:
        orig = ac.CLIENT_PATH
        ac.CLIENT_PATH = Path(td) / "does-not-exist.json"
        try:
            assert ac._refresh_token({"refresh_token": "stale-token"}) is None
        finally:
            ac.CLIENT_PATH = orig
