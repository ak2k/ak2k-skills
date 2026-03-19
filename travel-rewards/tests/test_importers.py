"""Tests for importer modules."""

from travel_rewards.importers.cardpointers import (
    extract_last_four,
    parse_frequency,
    slugify_card,
)
from travel_rewards.models import BenefitFrequency


def test_slugify_card():
    assert slugify_card("Chase Sapphire Reserve® (x5939)") == "chase-sapphire-reserve-x5939"
    assert slugify_card("American Express® Gold Card #2") == "american-express-gold-card-2"
    assert slugify_card("The Ritz-Carlton Rewards® Credit Card (x1012)") == "the-ritz-carlton-rewards-credit-card-x1012"


def test_extract_last_four():
    assert extract_last_four("Card (x5939)") == "5939"
    assert extract_last_four("Card (x42003)") == "42003"
    assert extract_last_four("Card without suffix") is None


def test_parse_frequency():
    assert parse_frequency("Once per month; something") == BenefitFrequency.MONTHLY
    assert parse_frequency("Once per calendar year; details") == BenefitFrequency.CALENDAR_YEAR
    assert parse_frequency("Once per cardmember year; details") == BenefitFrequency.CARDMEMBER_YEAR
    assert parse_frequency("Once per quarter; details") == BenefitFrequency.QUARTERLY
    assert parse_frequency("Once in January-June, once in July-December; details") == BenefitFrequency.SEMI_ANNUAL
    assert parse_frequency("Once every 4 years; details") == BenefitFrequency.ONE_TIME
    assert parse_frequency("Once per year; details") == BenefitFrequency.CARDMEMBER_YEAR
