"""All SQL reads and writes. Parameterized queries only."""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from travel_rewards.models import (
    Balance,
    Benefit,
    BenefitFrequency,
    BenefitUsage,
    Card,
    Certificate,
    Credit,
    SpendGoal,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_name(name: str) -> str:
    """Lowercase, strip, collapse spaces, remove punctuation."""
    s = name.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# --- Cards ---


def upsert_card(conn: sqlite3.Connection, card: Card) -> None:
    conn.execute(
        """INSERT INTO cards (card_id, name, issuer, last_four, annual_fee_cents,
                              anniversary_month, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(card_id) DO UPDATE SET
               name = COALESCE(excluded.name, cards.name),
               issuer = COALESCE(excluded.issuer, cards.issuer),
               last_four = COALESCE(excluded.last_four, cards.last_four),
               annual_fee_cents = excluded.annual_fee_cents,
               anniversary_month = COALESCE(excluded.anniversary_month, cards.anniversary_month),
               source = excluded.source,
               last_updated = excluded.last_updated""",
        (
            card.id,
            card.name,
            card.issuer,
            card.last_four,
            card.annual_fee_cents,
            card.anniversary_month,
            card.source,
            card.last_updated or _now(),
        ),
    )


def get_card(conn: sqlite3.Connection, card_id: str) -> Card | None:
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        return None
    return _row_to_card(row)


def list_cards(
    conn: sqlite3.Connection, *, issuer: str | None = None
) -> list[Card]:
    if issuer:
        rows = conn.execute(
            "SELECT * FROM cards WHERE issuer = ? ORDER BY name", (issuer,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM cards ORDER BY name").fetchall()
    return [_row_to_card(r) for r in rows]


def delete_card(conn: sqlite3.Connection, card_id: str) -> bool:
    cur = conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
    return cur.rowcount > 0


def _row_to_card(row: sqlite3.Row) -> Card:
    return Card(
        id=row["card_id"],
        name=row["name"],
        issuer=row["issuer"],
        last_four=row["last_four"],
        annual_fee_cents=row["annual_fee_cents"],
        anniversary_month=row["anniversary_month"],
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Benefits ---


def upsert_benefit(conn: sqlite3.Connection, benefit: Benefit) -> int:
    """Upsert by (card_id, normalized_name). Returns the benefit id."""
    conn.execute(
        """INSERT INTO benefits (card_id, display_name, normalized_name, category,
                                 value_cents, remaining_cents, frequency,
                                 enrolled_airline, notes, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(card_id, normalized_name) DO UPDATE SET
               category = COALESCE(excluded.category, benefits.category),
               value_cents = excluded.value_cents,
               remaining_cents = COALESCE(excluded.remaining_cents, benefits.remaining_cents),
               frequency = excluded.frequency,
               enrolled_airline = COALESCE(excluded.enrolled_airline, benefits.enrolled_airline),
               notes = COALESCE(excluded.notes, benefits.notes),
               source = excluded.source,
               last_updated = excluded.last_updated""",
        (
            benefit.card_id,
            benefit.display_name,
            benefit.normalized_name,
            benefit.category,
            benefit.value_cents,
            benefit.remaining_cents,
            benefit.frequency.value,
            benefit.enrolled_airline,
            benefit.notes,
            benefit.source,
            benefit.last_updated or _now(),
        ),
    )
    row = conn.execute(
        "SELECT id FROM benefits WHERE card_id = ? AND normalized_name = ?",
        (benefit.card_id, benefit.normalized_name),
    ).fetchone()
    return row["id"]


def list_benefits(
    conn: sqlite3.Connection, *, card_id: str | None = None
) -> list[Benefit]:
    if card_id:
        rows = conn.execute(
            "SELECT * FROM benefits WHERE card_id = ? ORDER BY display_name",
            (card_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM benefits ORDER BY card_id, display_name"
        ).fetchall()
    return [_row_to_benefit(r) for r in rows]


def get_benefit(conn: sqlite3.Connection, benefit_id: int) -> Benefit | None:
    row = conn.execute("SELECT * FROM benefits WHERE id = ?", (benefit_id,)).fetchone()
    if row is None:
        return None
    return _row_to_benefit(row)


def delete_benefit(conn: sqlite3.Connection, benefit_id: int) -> bool:
    cur = conn.execute("DELETE FROM benefits WHERE id = ?", (benefit_id,))
    return cur.rowcount > 0


def update_benefit(conn: sqlite3.Connection, benefit_id: int, **fields: object) -> bool:
    """Update specific fields on a benefit."""
    allowed = {
        "display_name", "category", "value_cents", "remaining_cents",
        "frequency", "enrolled_airline", "notes",
    }
    to_set = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not to_set:
        return False
    if "frequency" in to_set:
        to_set["frequency"] = BenefitFrequency(to_set["frequency"]).value
    to_set["last_updated"] = _now()
    cols = ", ".join(f"{k} = ?" for k in to_set)
    vals = list(to_set.values()) + [benefit_id]
    cur = conn.execute(f"UPDATE benefits SET {cols} WHERE id = ?", vals)  # noqa: S608
    return cur.rowcount > 0


def list_unused_benefits(
    conn: sqlite3.Connection, *, card_id: str | None = None
) -> list[Benefit]:
    """Benefits where remaining_cents > 0 or remaining_cents is NULL (never used)."""
    sql = """SELECT * FROM benefits
             WHERE (remaining_cents > 0 OR remaining_cents IS NULL)"""
    params: list[object] = []
    if card_id:
        sql += " AND card_id = ?"
        params.append(card_id)
    sql += " ORDER BY card_id, display_name"
    return [_row_to_benefit(r) for r in conn.execute(sql, params).fetchall()]


def _row_to_benefit(row: sqlite3.Row) -> Benefit:
    return Benefit(
        id=row["id"],
        card_id=row["card_id"],
        display_name=row["display_name"],
        normalized_name=row["normalized_name"],
        category=row["category"],
        value_cents=row["value_cents"],
        remaining_cents=row["remaining_cents"],
        frequency=BenefitFrequency(row["frequency"]),
        enrolled_airline=row["enrolled_airline"],
        notes=row["notes"],
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Benefit Usage ---


def record_usage(
    conn: sqlite3.Connection, benefit_id: int, amount_cents: int, source: str = "manual"
) -> int:
    """Record a benefit usage event. Returns the usage id."""
    cur = conn.execute(
        """INSERT INTO benefit_usage (benefit_id, amount_cents, used_at, source)
           VALUES (?, ?, ?, ?)""",
        (benefit_id, amount_cents, _now(), source),
    )
    # Update remaining_cents on the benefit
    conn.execute(
        """UPDATE benefits SET remaining_cents = COALESCE(remaining_cents, value_cents) - ?
           WHERE id = ?""",
        (amount_cents, benefit_id),
    )
    return cur.lastrowid  # type: ignore[return-value]


def undo_usage(conn: sqlite3.Connection, usage_id: int) -> bool:
    """Mark a usage record as undone (sets undone_at, restores remaining_cents)."""
    row = conn.execute(
        "SELECT benefit_id, amount_cents, undone_at FROM benefit_usage WHERE id = ?",
        (usage_id,),
    ).fetchone()
    if row is None or row["undone_at"] is not None:
        return False
    conn.execute(
        "UPDATE benefit_usage SET undone_at = ? WHERE id = ?", (_now(), usage_id)
    )
    conn.execute(
        "UPDATE benefits SET remaining_cents = COALESCE(remaining_cents, 0) + ? WHERE id = ?",
        (row["amount_cents"], row["benefit_id"]),
    )
    return True


def list_usage(
    conn: sqlite3.Connection, *, card_id: str | None = None
) -> list[BenefitUsage]:
    if card_id:
        sql = """SELECT bu.* FROM benefit_usage bu
                 JOIN benefits b ON bu.benefit_id = b.id
                 WHERE b.card_id = ?
                 ORDER BY bu.used_at DESC"""
        rows = conn.execute(sql, (card_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM benefit_usage ORDER BY used_at DESC"
        ).fetchall()
    return [_row_to_usage(r) for r in rows]


def _row_to_usage(row: sqlite3.Row) -> BenefitUsage:
    return BenefitUsage(
        id=row["id"],
        benefit_id=row["benefit_id"],
        amount_cents=row["amount_cents"],
        used_at=row["used_at"],
        undone_at=row["undone_at"],
        source=row["source"],
    )


# --- Balances ---


def upsert_balance(conn: sqlite3.Connection, balance: Balance) -> None:
    conn.execute(
        """INSERT INTO balances (program_name, program_type, amount, unit,
                                 status, status_expiry, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(program_name) DO UPDATE SET
               program_type = COALESCE(excluded.program_type, balances.program_type),
               amount = excluded.amount,
               unit = excluded.unit,
               status = COALESCE(excluded.status, balances.status),
               status_expiry = COALESCE(excluded.status_expiry, balances.status_expiry),
               source = excluded.source,
               last_updated = excluded.last_updated""",
        (
            balance.program_name,
            balance.program_type,
            balance.amount,
            balance.unit,
            balance.status,
            balance.status_expiry,
            balance.source,
            balance.last_updated or _now(),
        ),
    )


def list_balances(conn: sqlite3.Connection) -> list[Balance]:
    rows = conn.execute(
        "SELECT * FROM balances ORDER BY program_name"
    ).fetchall()
    return [_row_to_balance(r) for r in rows]


def set_balance(
    conn: sqlite3.Connection, program_name: str, amount: int
) -> bool:
    cur = conn.execute(
        "UPDATE balances SET amount = ?, last_updated = ? WHERE program_name = ?",
        (amount, _now(), program_name),
    )
    return cur.rowcount > 0


def _row_to_balance(row: sqlite3.Row) -> Balance:
    return Balance(
        id=row["id"],
        program_name=row["program_name"],
        program_type=row["program_type"],
        amount=row["amount"],
        unit=row["unit"],
        status=row["status"],
        status_expiry=row["status_expiry"],
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Credits ---


def add_credit(conn: sqlite3.Connection, credit: Credit) -> int:
    cur = conn.execute(
        """INSERT INTO credits (name, issuer, value_cents, remaining_cents,
                                expiration, passenger, confirmation, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            credit.name,
            credit.issuer,
            credit.value_cents,
            credit.remaining_cents,
            credit.expiration,
            credit.passenger,
            credit.confirmation,
            credit.source or "manual",
            credit.last_updated or _now(),
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def list_credits(conn: sqlite3.Connection) -> list[Credit]:
    rows = conn.execute(
        "SELECT * FROM credits WHERE remaining_cents > 0 ORDER BY expiration"
    ).fetchall()
    return [_row_to_credit(r) for r in rows]


def use_credit(conn: sqlite3.Connection, credit_id: int, amount_cents: int) -> bool:
    cur = conn.execute(
        """UPDATE credits SET remaining_cents = remaining_cents - ?,
                              last_updated = ?
           WHERE id = ? AND remaining_cents >= ?""",
        (amount_cents, _now(), credit_id, amount_cents),
    )
    return cur.rowcount > 0


def upsert_credit(conn: sqlite3.Connection, credit: Credit) -> None:
    """Upsert for importers — matches on name + issuer."""
    conn.execute(
        """INSERT INTO credits (name, issuer, value_cents, remaining_cents,
                                expiration, passenger, confirmation, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT DO NOTHING""",
        (
            credit.name,
            credit.issuer,
            credit.value_cents,
            credit.remaining_cents,
            credit.expiration,
            credit.passenger,
            credit.confirmation,
            credit.source,
            credit.last_updated or _now(),
        ),
    )


def _row_to_credit(row: sqlite3.Row) -> Credit:
    return Credit(
        id=row["id"],
        name=row["name"],
        issuer=row["issuer"],
        value_cents=row["value_cents"],
        remaining_cents=row["remaining_cents"],
        expiration=row["expiration"],
        passenger=row["passenger"],
        confirmation=row["confirmation"],
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Certificates ---


def add_certificate(conn: sqlite3.Connection, cert: Certificate) -> int:
    cur = conn.execute(
        """INSERT INTO certificates (program_name, name, details, expiration,
                                     used, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            cert.program_name,
            cert.name,
            cert.details,
            cert.expiration,
            int(cert.used),
            cert.source or "manual",
            cert.last_updated or _now(),
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def list_certificates(conn: sqlite3.Connection) -> list[Certificate]:
    rows = conn.execute(
        "SELECT * FROM certificates ORDER BY expiration"
    ).fetchall()
    return [_row_to_certificate(r) for r in rows]


def use_certificate(conn: sqlite3.Connection, cert_id: int) -> bool:
    cur = conn.execute(
        "UPDATE certificates SET used = 1, last_updated = ? WHERE id = ? AND used = 0",
        (_now(), cert_id),
    )
    return cur.rowcount > 0


def upsert_certificate(conn: sqlite3.Connection, cert: Certificate) -> None:
    """Upsert for importers."""
    conn.execute(
        """INSERT INTO certificates (program_name, name, details, expiration,
                                     used, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT DO NOTHING""",
        (
            cert.program_name,
            cert.name,
            cert.details,
            cert.expiration,
            int(cert.used),
            cert.source,
            cert.last_updated or _now(),
        ),
    )


def _row_to_certificate(row: sqlite3.Row) -> Certificate:
    return Certificate(
        id=row["id"],
        program_name=row["program_name"],
        name=row["name"],
        details=row["details"],
        expiration=row["expiration"],
        used=bool(row["used"]),
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Spend Goals ---


def add_spend_goal(conn: sqlite3.Connection, goal: SpendGoal) -> int:
    cur = conn.execute(
        """INSERT INTO spend_goals (card_id, target_cents, current_cents,
                                    deadline, reward, source, last_updated)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            goal.card_id,
            goal.target_cents,
            goal.current_cents,
            goal.deadline,
            goal.reward,
            goal.source or "manual",
            goal.last_updated or _now(),
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def list_spend_goals(conn: sqlite3.Connection) -> list[SpendGoal]:
    rows = conn.execute(
        "SELECT * FROM spend_goals ORDER BY deadline"
    ).fetchall()
    return [_row_to_spend_goal(r) for r in rows]


def update_spend_goal(
    conn: sqlite3.Connection, goal_id: int, amount_cents: int
) -> bool:
    """Add incremental spend to a goal."""
    cur = conn.execute(
        """UPDATE spend_goals SET current_cents = current_cents + ?,
                                  last_updated = ?
           WHERE id = ?""",
        (amount_cents, _now(), goal_id),
    )
    return cur.rowcount > 0


def _row_to_spend_goal(row: sqlite3.Row) -> SpendGoal:
    return SpendGoal(
        id=row["id"],
        card_id=row["card_id"],
        target_cents=row["target_cents"],
        current_cents=row["current_cents"],
        deadline=row["deadline"],
        reward=row["reward"],
        source=row["source"],
        last_updated=row["last_updated"],
    )


# --- Expiring Items ---


def list_expiring(conn: sqlite3.Connection, days: int = 30) -> dict[str, list[object]]:
    """Items expiring within the given number of days."""
    sql_date = f"+{days} days"
    result: dict[str, list[object]] = {"credits": [], "certificates": [], "balances": []}

    for row in conn.execute(
        """SELECT * FROM credits
           WHERE remaining_cents > 0 AND expiration IS NOT NULL
                 AND date(expiration) <= date('now', ?)
           ORDER BY expiration""",
        (sql_date,),
    ).fetchall():
        result["credits"].append(_row_to_credit(row))

    for row in conn.execute(
        """SELECT * FROM certificates
           WHERE used = 0 AND expiration IS NOT NULL
                 AND date(expiration) <= date('now', ?)
           ORDER BY expiration""",
        (sql_date,),
    ).fetchall():
        result["certificates"].append(_row_to_certificate(row))

    for row in conn.execute(
        """SELECT * FROM balances
           WHERE status_expiry IS NOT NULL
                 AND date(status_expiry) <= date('now', ?)
           ORDER BY status_expiry""",
        (sql_date,),
    ).fetchall():
        result["balances"].append(_row_to_balance(row))

    return result


# --- Status ---


def get_status(conn: sqlite3.Connection) -> dict[str, object]:
    """Compact summary for Claude context bootstrapping."""
    cards_count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    unused_count = conn.execute(
        "SELECT COUNT(*) FROM benefits WHERE remaining_cents > 0 OR remaining_cents IS NULL"
    ).fetchone()[0]
    expiring_30 = 0
    for table, col, cond in [
        ("credits", "expiration", "remaining_cents > 0"),
        ("certificates", "expiration", "used = 0"),
        ("balances", "status_expiry", "1=1"),
    ]:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {cond} AND {col} IS NOT NULL "  # noqa: S608
            f"AND date({col}) <= date('now', '+30 days')"
        ).fetchone()
        expiring_30 += row[0]

    # Last import times per source
    last_imports: dict[str, str] = {}
    for row in conn.execute(
        "SELECT source, MAX(last_updated) as latest FROM cards GROUP BY source"
    ).fetchall():
        last_imports[row["source"]] = row["latest"]

    return {
        "cards": cards_count,
        "unused_benefits": unused_count,
        "expiring_soon": expiring_30,
        "last_import": last_imports,
    }


# --- Search helpers ---


def find_card_fuzzy(conn: sqlite3.Connection, query: str) -> list[Card]:
    """Find cards matching a partial name or id."""
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM cards WHERE card_id LIKE ? OR name LIKE ? ORDER BY name",
        (q, q),
    ).fetchall()
    return [_row_to_card(r) for r in rows]


def find_benefit_by_card_and_name(
    conn: sqlite3.Connection, card_id: str, benefit_query: str
) -> Benefit | None:
    """Find a benefit by card_id and partial name match."""
    norm = normalize_name(benefit_query)
    row = conn.execute(
        "SELECT * FROM benefits WHERE card_id = ? AND normalized_name LIKE ?",
        (card_id, f"%{norm}%"),
    ).fetchone()
    if row is None:
        return None
    return _row_to_benefit(row)
