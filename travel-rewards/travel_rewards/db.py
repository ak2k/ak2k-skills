"""Database connection factory and schema migrations."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

MIGRATIONS: list[list[str]] = [
    [
        # Version 1: initial schema
        """CREATE TABLE cards (
            card_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            issuer TEXT,
            last_four TEXT,
            annual_fee_cents INTEGER NOT NULL DEFAULT 0,
            anniversary_month INTEGER CHECK(anniversary_month BETWEEN 1 AND 12),
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )""",
        """CREATE TABLE benefits (
            id INTEGER PRIMARY KEY,
            card_id TEXT NOT NULL REFERENCES cards(card_id) ON UPDATE CASCADE ON DELETE CASCADE,
            display_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            category TEXT,
            value_cents INTEGER NOT NULL DEFAULT 0,
            remaining_cents INTEGER CHECK(remaining_cents >= 0),
            frequency TEXT NOT NULL CHECK(frequency IN (
                'calendar_year', 'cardmember_year', 'monthly', 'quarterly',
                'semi_annual', 'one_time'
            )),
            enrolled_airline TEXT,
            notes TEXT,
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            UNIQUE(card_id, normalized_name)
        )""",
        """CREATE TABLE benefit_usage (
            id INTEGER PRIMARY KEY,
            benefit_id INTEGER NOT NULL REFERENCES benefits(id) ON DELETE CASCADE,
            amount_cents INTEGER NOT NULL,
            used_at TEXT NOT NULL,
            undone_at TEXT,
            source TEXT NOT NULL DEFAULT 'manual'
        )""",
        """CREATE TABLE balances (
            id INTEGER PRIMARY KEY,
            program_name TEXT NOT NULL,
            program_type TEXT CHECK(program_type IN ('airline', 'hotel', 'bank', 'other')),
            amount INTEGER NOT NULL CHECK(amount >= 0),
            unit TEXT NOT NULL DEFAULT 'points',
            status TEXT,
            status_expiry TEXT,
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            UNIQUE(program_name)
        )""",
        """CREATE TABLE credits (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            issuer TEXT,
            value_cents INTEGER NOT NULL,
            remaining_cents INTEGER NOT NULL CHECK(remaining_cents >= 0),
            expiration TEXT,
            passenger TEXT,
            confirmation TEXT,
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )""",
        """CREATE TABLE certificates (
            id INTEGER PRIMARY KEY,
            program_name TEXT,
            name TEXT NOT NULL,
            details TEXT,
            expiration TEXT,
            used INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )""",
        """CREATE TABLE spend_goals (
            id INTEGER PRIMARY KEY,
            card_id TEXT NOT NULL REFERENCES cards(card_id) ON UPDATE CASCADE,
            target_cents INTEGER NOT NULL,
            current_cents INTEGER NOT NULL DEFAULT 0,
            deadline TEXT,
            reward TEXT,
            source TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )""",
        "CREATE INDEX idx_benefits_card ON benefits(card_id)",
        "CREATE INDEX idx_benefit_usage_benefit ON benefit_usage(benefit_id)",
        "CREATE INDEX idx_credits_expiration ON credits(expiration)",
        "CREATE INDEX idx_certificates_expiration ON certificates(expiration)",
    ],
]


def connect(db_path: Path) -> sqlite3.Connection:
    """Create a connection with WAL mode, FK enforcement, and busy timeout."""
    db_path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    conn = sqlite3.connect(str(db_path), autocommit=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.autocommit = False
    conn.row_factory = sqlite3.Row
    # Set file permissions on creation
    if db_path.exists():
        os.chmod(db_path, 0o600)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Run pending migrations using PRAGMA user_version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for i, statements in enumerate(MIGRATIONS[current:], start=current):
        for statement in statements:
            conn.execute(statement)
        version = int(i + 1)
        conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()
