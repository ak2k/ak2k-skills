"""Data models for travel rewards entities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class BenefitFrequency(StrEnum):
    CALENDAR_YEAR = "calendar_year"
    CARDMEMBER_YEAR = "cardmember_year"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ONE_TIME = "one_time"


@dataclass(frozen=True, slots=True)
class Card:
    id: str
    name: str
    issuer: str | None = None
    last_four: str | None = None
    annual_fee_cents: int = 0
    anniversary_month: int | None = None
    source: str = ""
    last_updated: str = ""


@dataclass(frozen=True, slots=True)
class Benefit:
    id: int | None = None
    card_id: str = ""
    display_name: str = ""
    normalized_name: str = ""
    category: str | None = None
    value_cents: int = 0
    remaining_cents: int | None = None
    frequency: BenefitFrequency = BenefitFrequency.CALENDAR_YEAR
    enrolled_airline: str | None = None
    notes: str | None = None
    source: str = ""
    last_updated: str = ""


@dataclass(frozen=True, slots=True)
class BenefitUsage:
    id: int | None = None
    benefit_id: int = 0
    amount_cents: int = 0
    used_at: str = ""
    undone_at: str | None = None
    source: str = "manual"


@dataclass(frozen=True, slots=True)
class Balance:
    id: int | None = None
    program_name: str = ""
    program_type: str | None = None
    amount: int = 0
    unit: str = "points"
    status: str | None = None
    status_expiry: str | None = None
    source: str = ""
    last_updated: str = ""


@dataclass(frozen=True, slots=True)
class Credit:
    id: int | None = None
    name: str = ""
    issuer: str | None = None
    value_cents: int = 0
    remaining_cents: int = 0
    expiration: str | None = None
    passenger: str | None = None
    confirmation: str | None = None
    source: str = ""
    last_updated: str = ""


@dataclass(frozen=True, slots=True)
class Certificate:
    id: int | None = None
    program_name: str | None = None
    name: str = ""
    details: str | None = None
    expiration: str | None = None
    used: bool = False
    source: str = ""
    last_updated: str = ""


@dataclass(frozen=True, slots=True)
class SpendGoal:
    id: int | None = None
    card_id: str = ""
    target_cents: int = 0
    current_cents: int = 0
    deadline: str | None = None
    reward: str | None = None
    source: str = ""
    last_updated: str = ""
