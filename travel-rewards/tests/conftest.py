"""Test fixtures for travel-rewards."""

import pytest
from click.testing import CliRunner

from travel_rewards.cli import cli
from travel_rewards.db import connect, migrate


@pytest.fixture
def db(tmp_path):
    """Database connection mirroring production (WAL, FK, busy_timeout)."""
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def invoke(tmp_path):
    """Click CLI test runner pointing at a temp data directory."""
    runner = CliRunner()
    data_dir = str(tmp_path / "config")

    def _invoke(*args):
        return runner.invoke(cli, ["--data-dir", data_dir] + list(args))

    return _invoke


@pytest.fixture
def invoke_json(tmp_path):
    """Click CLI test runner with --json flag."""
    runner = CliRunner()
    data_dir = str(tmp_path / "config")

    def _invoke(*args):
        return runner.invoke(cli, ["--json", "--data-dir", data_dir] + list(args))

    return _invoke
