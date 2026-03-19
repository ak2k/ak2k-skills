"""Tests for database connection and migrations."""

from travel_rewards.db import connect, migrate


def test_migrate_creates_tables(db):
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = [r["name"] for r in tables]
    assert "cards" in names
    assert "benefits" in names
    assert "benefit_usage" in names
    assert "balances" in names
    assert "credits" in names
    assert "certificates" in names
    assert "spend_goals" in names


def test_user_version_set(db):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1


def test_foreign_keys_enabled(db):
    fk = db.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_wal_mode(db):
    mode = db.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_migrate_idempotent(tmp_path):
    conn = connect(tmp_path / "test.db")
    migrate(conn)
    migrate(conn)  # Should not fail
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == 1
    conn.close()
