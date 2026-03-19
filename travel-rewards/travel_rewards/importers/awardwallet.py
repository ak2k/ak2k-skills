"""Import balances, credits, certificates, and spend goals from AwardWallet .xls export."""

from __future__ import annotations

import re
from pathlib import Path

import xlrd
import yaml

from travel_rewards.models import Balance, Certificate, Credit, SpendGoal

SOURCE = "awardwallet"

# AwardWallet "Accounts" export column headers
COL_ACCOUNT_ID = "Account Id / Sub Id"
COL_TYPE = "Type"
COL_PROGRAM = "Award Program"
COL_BALANCE = "Balance"
COL_CASH_EQUIV = "Cash Equivalent"
COL_EXPIRATION = "Expiration"
COL_STATUS = "Status"
COL_STATUS_EXPIRY = "Status expiration"
COL_NAME = "Name"
COL_LAST_UPDATE = "Last Update"

# Type values in AwardWallet exports
TYPE_AIRLINE = "Airlines"
TYPE_HOTEL = "Hotels"
TYPE_BANK = "Credit Cards"
TYPE_OTHER = "Other"

TYPE_MAP = {
    TYPE_AIRLINE: "airline",
    TYPE_HOTEL: "hotel",
    TYPE_BANK: "bank",
    TYPE_OTHER: "other",
}


def _parse_balance_int(val: object) -> int:
    """Parse a balance value like '184,230' or 30.0 to integer."""
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        s = val.strip().replace(",", "")
        if not s or s.lower() in ("n/a", "unknown", "-"):
            return 0
        try:
            return int(float(s))
        except ValueError:
            return 0
    return 0


def _parse_cash_cents(val: object) -> int:
    """Parse cash equivalent like '$3,445' to integer cents."""
    if isinstance(val, (int, float)):
        return int(val * 100)
    if isinstance(val, str):
        s = val.strip().replace(",", "").replace("$", "")
        if not s or s.lower() in ("n/a", "unknown", "-"):
            return 0
        try:
            return int(float(s) * 100)
        except ValueError:
            return 0
    return 0


def _parse_last_update(val: object) -> str:
    """Parse AwardWallet 'Last Update' like 'Friday, January 9, 2026' to ISO 8601."""
    if not val or not isinstance(val, str) or not val.strip():
        return ""
    s = val.strip()
    # Try parsing "DayOfWeek, Month Day, Year" format
    for fmt in ("%A, %B %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            from datetime import datetime, timezone

            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            continue
    return s  # Return as-is if unparseable


def _is_sub_account(account_id: str) -> bool:
    """Sub-accounts start with whitespace and '/'."""
    return account_id.strip().startswith("/")


def load_card_mapping(config_dir: Path) -> dict[str, str]:
    """Load card_mapping.yaml that maps AwardWallet 5-digit suffixes to card IDs."""
    mapping_path = config_dir / "card_mapping.yaml"
    if not mapping_path.exists():
        return {}
    with open(mapping_path) as f:
        data = yaml.safe_load(f)  # safe_load only — never yaml.load()
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def import_accounts(
    xls_path: Path,
    config_dir: Path,
) -> tuple[list[Balance], list[Credit], list[Certificate], list[SpendGoal], list[str]]:
    """Parse AwardWallet .xls export and return structured data.

    Returns (balances, credits, certificates, spend_goals, warnings).
    """
    warnings: list[str] = []
    card_mapping = load_card_mapping(config_dir)

    wb = xlrd.open_workbook(str(xls_path), ignore_workbook_corruption=True)
    sheet = wb.sheet_by_index(0)

    # Find header row and build column index
    headers: dict[str, int] = {}
    header_row = 0
    for r in range(min(5, sheet.nrows)):
        val = sheet.cell_value(r, 0)
        if isinstance(val, str) and val.strip() == COL_ACCOUNT_ID:
            header_row = r
            for c in range(sheet.ncols):
                h = str(sheet.cell_value(r, c)).strip()
                if h:
                    headers[h] = c
            break

    if not headers:
        warnings.append("Could not find header row in AwardWallet export")
        return [], [], [], [], warnings

    balances: list[Balance] = []
    credits: list[Credit] = []
    certificates: list[Certificate] = []
    spend_goals: list[SpendGoal] = []

    current_parent_program: str | None = None

    for r in range(header_row + 1, sheet.nrows):
        row_data = {h: sheet.cell_value(r, c) for h, c in headers.items()}
        account_id = str(row_data.get(COL_ACCOUNT_ID, "")).strip()

        if not account_id:
            continue

        program = str(row_data.get(COL_PROGRAM, "")).strip()
        account_type = str(row_data.get(COL_TYPE, "")).strip()

        if _is_sub_account(str(row_data.get(COL_ACCOUNT_ID, ""))):
            # Sub-account: use parent program as context
            if program and current_parent_program:
                # Sub-accounts like "eUpgrade credits" under Air Canada
                balance_val = _parse_balance_int(row_data.get(COL_BALANCE, 0))
                if balance_val > 0:
                    balances.append(Balance(
                        program_name=f"{current_parent_program} - {program}",
                        program_type=TYPE_MAP.get(account_type),
                        amount=balance_val,
                        unit=_guess_unit(program),
                        source=SOURCE,
                        last_updated=_parse_last_update(row_data.get(COL_LAST_UPDATE, "")),
                    ))
            continue

        # Parent account
        current_parent_program = program
        if not program:
            continue

        balance_val = _parse_balance_int(row_data.get(COL_BALANCE, 0))
        status = str(row_data.get(COL_STATUS, "")).strip() or None
        status_expiry = str(row_data.get(COL_STATUS_EXPIRY, "")).strip() or None
        expiration = str(row_data.get(COL_EXPIRATION, "")).strip() or None

        last_update = _parse_last_update(row_data.get(COL_LAST_UPDATE, ""))

        if balance_val > 0 or status:
            balances.append(Balance(
                program_name=program,
                program_type=TYPE_MAP.get(account_type),
                amount=balance_val,
                unit=_guess_unit(program),
                status=status,
                status_expiry=status_expiry,
                source=SOURCE,
                last_updated=last_update,
            ))

    return balances, credits, certificates, spend_goals, warnings


def _guess_unit(program: str) -> str:
    """Guess the unit for a program based on name conventions."""
    p = program.lower()
    if "miles" in p or "mileage" in p:
        return "miles"
    if "points" in p or "rewards" in p:
        return "points"
    if "credit" in p or "cash" in p:
        return "dollars"
    return "points"
