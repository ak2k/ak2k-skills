"""Import cards and benefits from CardPointers local SQLite database."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from travel_rewards.models import Benefit, BenefitFrequency, Card
from travel_rewards.repository import normalize_name

DEFAULT_DB_PATH = Path.home() / "Library/Group Containers/group.getcardpointers.app/cardpointers.sqlite"

SOURCE = "cardpointers"


def slugify_card(title: str) -> str:
    """Generate a stable card ID from the title.

    Strips special chars, lowercases, joins with hyphens.
    Preserves (xNNNN) suffix if present for disambiguation.
    """
    s = title.strip()
    s = re.sub(r"[®™©]", "", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def parse_frequency(subtitle: str) -> BenefitFrequency:
    """Parse frequency from CardPointers benefit subtitle text."""
    s = subtitle.lower().strip()

    if s.startswith("once per month"):
        return BenefitFrequency.MONTHLY
    if s.startswith("once per quarter"):
        return BenefitFrequency.QUARTERLY
    if s.startswith("once per calendar year"):
        return BenefitFrequency.CALENDAR_YEAR
    if s.startswith("once per cardmember year"):
        return BenefitFrequency.CARDMEMBER_YEAR
    if s.startswith("once per year"):
        return BenefitFrequency.CARDMEMBER_YEAR
    if "january-june" in s or "semi-annual" in s:
        return BenefitFrequency.SEMI_ANNUAL
    if "every 4 years" in s or "every 5 years" in s:
        return BenefitFrequency.ONE_TIME
    if "once" in s:
        return BenefitFrequency.CALENDAR_YEAR
    if "per month" in s or "monthly" in s or "per monthly billing" in s:
        return BenefitFrequency.MONTHLY
    if "annually" in s or "every calendar year" in s or "per year" in s:
        return BenefitFrequency.CALENDAR_YEAR

    raise ValueError(f"Unknown frequency in subtitle: {subtitle!r}")


def extract_last_four(title: str) -> str | None:
    """Extract (xNNNN) or (xNNNNN) suffix from card title."""
    m = re.search(r"\(x(\d{4,5})\)", title)
    return m.group(1) if m else None


def import_cards_and_benefits(
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[list[Card], list[Benefit], list[str]]:
    """Read CardPointers SQLite and return cards, benefits, and warnings.

    Opens the database in read-only mode to prevent any writes.
    """
    warnings: list[str] = []

    if not db_path.exists():
        warnings.append(f"CardPointers database not found at {db_path}")
        return [], [], warnings

    uri = f"file:{db_path}?mode=ro"
    cp_conn = sqlite3.connect(uri, uri=True)
    cp_conn.row_factory = sqlite3.Row

    try:
        cards = _read_cards(cp_conn, warnings)
        benefits = _read_benefits(cp_conn, cards, warnings)
    finally:
        cp_conn.close()

    return cards, benefits, warnings


def _read_cards(
    conn: sqlite3.Connection, warnings: list[str]
) -> list[Card]:
    """Read active cards (ZSTATUS=2) from CardPointers."""
    rows = conn.execute(
        """SELECT ZTITLE, ZBANKNAME, ZFEE, ZSTATUS, Z_PK
           FROM ZDBCARDPARENT WHERE ZSTATUS = 2"""
    ).fetchall()

    cards: list[Card] = []
    for row in rows:
        title = row["ZTITLE"]
        if not title:
            warnings.append(f"Card with PK={row['Z_PK']} has no title, skipping")
            continue

        last_four = extract_last_four(title)
        card_id = slugify_card(title)

        cards.append(Card(
            id=card_id,
            name=title,
            issuer=row["ZBANKNAME"] or None,
            last_four=last_four,
            annual_fee_cents=int(row["ZFEE"] or 0) * 100,
            source=SOURCE,
        ))

    return cards


def _read_benefits(
    conn: sqlite3.Connection,
    cards: list[Card],
    warnings: list[str],
) -> list[Benefit]:
    """Read standard benefits (ZSTANDARD=1) joined to active cards.

    Benefits link to cards via ZINVENTORY = card.Z_PK (Core Data convention).
    """
    # Build PK → card_id map
    pk_rows = conn.execute(
        "SELECT Z_PK, ZTITLE FROM ZDBCARDPARENT WHERE ZSTATUS = 2"
    ).fetchall()
    pk_to_card_id: dict[int, str] = {}
    for row in pk_rows:
        if row["ZTITLE"]:
            pk_to_card_id[row["Z_PK"]] = slugify_card(row["ZTITLE"])

    rows = conn.execute(
        """SELECT o.ZTITLE, o.ZSUBTITLE, o.ZVALUE, o.ZTOTAL_AVAILABLE,
                  o.ZTOTAL_USED, o.ZINVENTORY
           FROM ZDBOFFERPARENT o
           WHERE o.ZSTANDARD = 1 AND o.ZINVENTORY IS NOT NULL"""
    ).fetchall()

    benefits: list[Benefit] = []
    for row in rows:
        card_pk = row["ZINVENTORY"]
        if card_pk not in pk_to_card_id:
            continue

        card_id = pk_to_card_id[card_pk]
        title = row["ZTITLE"] or ""
        subtitle = row["ZSUBTITLE"] or ""

        if not title:
            continue

        try:
            frequency = parse_frequency(subtitle)
        except ValueError as e:
            warnings.append(str(e))
            frequency = BenefitFrequency.CALENDAR_YEAR

        value_cents = int((row["ZVALUE"] or 0) * 100)
        total_available = row["ZTOTAL_AVAILABLE"]
        total_used = row["ZTOTAL_USED"] or 0
        remaining = int((total_available - total_used) * 100) if total_available else None

        benefits.append(Benefit(
            card_id=card_id,
            display_name=title,
            normalized_name=normalize_name(title),
            value_cents=value_cents,
            remaining_cents=remaining,
            frequency=frequency,
            notes=subtitle.split(";", 1)[1].strip() if ";" in subtitle else None,
            source=SOURCE,
        ))

    return benefits
