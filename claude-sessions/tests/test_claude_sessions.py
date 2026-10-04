"""Regression tests for claude_sessions.py.

Run with pytest; the nix build runs them via pytestCheckHook. Bare test
functions, so `unittest discover` collects nothing. Plain asserts and stdlib
only — matching atlassian-cli/tests, and keeping pytest out of the treefmt
mypy env.

parse_timestamp is the funnel every session record passes through, and each
shape below comes from a different producer: epoch millis, the `Z`-suffixed
ISO strings Claude Code writes, offset-naive strings, and junk. A regression
here does not raise — it silently drops sessions from the listing.
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "claude_sessions.py"
_spec = importlib.util.spec_from_file_location("claude_sessions_under_test", SRC)
assert _spec and _spec.loader
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


def test_epoch_millis_becomes_utc_aware():
    """Millis are unambiguous instants, so the result must carry UTC rather
    than pick up whatever timezone the machine happens to sit in."""
    ts = cs.parse_timestamp(1_755_892_539_000)
    assert ts is not None
    assert ts.tzinfo is not None, "epoch millis must produce an aware datetime"
    assert ts.utcoffset() == timedelta(0)
    assert ts == datetime(2025, 8, 22, 19, 55, 39, tzinfo=UTC)


def test_trailing_z_parses_as_utc():
    """The `Z` suffix is what Claude Code writes. fromisoformat has handled it
    natively since 3.11, which is why no pre-`replace` is needed to get here."""
    ts = cs.parse_timestamp("2026-08-22T20:15:39Z")
    assert ts == datetime(2026, 8, 22, 20, 15, 39, tzinfo=UTC)
    assert ts is not None and ts.utcoffset() == timedelta(0)


def test_naive_iso_string_stays_naive():
    """No offset in, no offset out — inventing one would silently shift a
    session's age by the local UTC offset. The naive literal below is the
    assertion, so it carries no tzinfo on purpose."""
    ts = cs.parse_timestamp("2026-08-22T20:15:39")
    assert ts == datetime(2026, 8, 22, 20, 15, 39)  # noqa: DTZ001
    assert ts is not None and ts.tzinfo is None


def test_unparseable_string_is_none():
    assert cs.parse_timestamp("not-a-timestamp") is None


def test_missing_timestamp_is_none():
    assert cs.parse_timestamp(None) is None
