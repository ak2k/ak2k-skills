"""Tests for repository operations."""

import json

from travel_rewards.models import (
    Balance,
    Benefit,
    BenefitFrequency,
    Card,
    Certificate,
    Credit,
    SpendGoal,
)
from travel_rewards.repository import (
    add_certificate,
    add_credit,
    add_spend_goal,
    delete_card,
    find_benefit_by_card_and_name,
    find_card_fuzzy,
    get_card,
    get_status,
    list_balances,
    list_benefits,
    list_cards,
    list_certificates,
    list_credits,
    list_expiring,
    list_spend_goals,
    list_unused_benefits,
    list_usage,
    normalize_name,
    record_usage,
    set_balance,
    undo_usage,
    update_spend_goal,
    upsert_balance,
    upsert_benefit,
    upsert_card,
    use_certificate,
    use_credit,
)


def _make_card(card_id="test-card", name="Test Card", **kwargs):
    return Card(id=card_id, name=name, source="test", **kwargs)


def _make_benefit(card_id="test-card", name="Test Benefit", frequency=BenefitFrequency.CALENDAR_YEAR, **kwargs):
    return Benefit(
        card_id=card_id,
        display_name=name,
        normalized_name=normalize_name(name),
        value_cents=5000,
        frequency=frequency,
        source="test",
        **kwargs,
    )


# --- Card tests ---


def test_upsert_card_insert(db):
    card = _make_card()
    upsert_card(db, card)
    db.commit()
    result = get_card(db, "test-card")
    assert result is not None
    assert result.name == "Test Card"


def test_upsert_card_idempotent(db):
    card = _make_card()
    upsert_card(db, card)
    upsert_card(db, card)
    db.commit()
    cards = list_cards(db)
    assert len(cards) == 1


def test_delete_card_cascades_benefits(db):
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit())
    db.commit()
    assert len(list_benefits(db, card_id="test-card")) == 1

    delete_card(db, "test-card")
    db.commit()
    assert len(list_benefits(db, card_id="test-card")) == 0


def test_fk_cascade_on_update(db):
    """ON UPDATE CASCADE: renaming card_id updates child rows."""
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit())
    db.commit()

    db.execute("UPDATE cards SET card_id = 'renamed-card' WHERE card_id = 'test-card'")
    db.commit()

    benefits = list_benefits(db, card_id="renamed-card")
    assert len(benefits) == 1
    assert benefits[0].card_id == "renamed-card"


def test_find_card_fuzzy(db):
    upsert_card(db, _make_card(card_id="chase-sapphire-reserve", name="Chase Sapphire Reserve"))
    db.commit()
    results = find_card_fuzzy(db, "sapphire")
    assert len(results) == 1
    assert results[0].id == "chase-sapphire-reserve"


# --- Benefit tests ---


def test_upsert_benefit_idempotent(db):
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit())
    upsert_benefit(db, _make_benefit())
    db.commit()
    benefits = list_benefits(db, card_id="test-card")
    assert len(benefits) == 1


def test_benefit_frequency_enum(db):
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit(frequency=BenefitFrequency.MONTHLY))
    db.commit()
    benefits = list_benefits(db, card_id="test-card")
    assert benefits[0].frequency == BenefitFrequency.MONTHLY


def test_unused_benefits(db):
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit(remaining_cents=5000))
    upsert_benefit(db, _make_benefit(
        name="Used Benefit", remaining_cents=0
    ))
    db.commit()
    unused = list_unused_benefits(db)
    assert len(unused) == 1
    assert unused[0].display_name == "Test Benefit"


# --- Usage tests ---


def test_record_and_undo_usage(db):
    upsert_card(db, _make_card())
    bid = upsert_benefit(db, _make_benefit(remaining_cents=5000))
    db.commit()

    usage_id = record_usage(db, bid, 2000)
    db.commit()

    # Check remaining decreased
    benefits = list_benefits(db, card_id="test-card")
    assert benefits[0].remaining_cents == 3000

    # Check usage recorded
    usages = list_usage(db)
    assert len(usages) == 1
    assert usages[0].amount_cents == 2000

    # Undo
    assert undo_usage(db, usage_id)
    db.commit()

    # Check remaining restored
    benefits = list_benefits(db, card_id="test-card")
    assert benefits[0].remaining_cents == 5000

    # Can't undo twice
    assert not undo_usage(db, usage_id)


# --- Balance tests ---


def test_upsert_balance(db):
    upsert_balance(db, Balance(
        program_name="Chase Ultimate Rewards",
        program_type="bank",
        amount=100000,
        source="test",
    ))
    db.commit()
    balances = list_balances(db)
    assert len(balances) == 1
    assert balances[0].amount == 100000


def test_set_balance(db):
    upsert_balance(db, Balance(
        program_name="Test Program", amount=1000, source="test"
    ))
    db.commit()
    assert set_balance(db, "Test Program", 2000)
    db.commit()
    balances = list_balances(db)
    assert balances[0].amount == 2000


# --- Credit tests ---


def test_add_and_use_credit(db):
    cid = add_credit(db, Credit(
        name="Delta Credit", value_cents=10000,
        remaining_cents=10000, source="test",
    ))
    db.commit()
    assert use_credit(db, cid, 3000)
    db.commit()
    credits = list_credits(db)
    assert credits[0].remaining_cents == 7000


# --- Certificate tests ---


def test_add_and_use_certificate(db):
    cid = add_certificate(db, Certificate(
        program_name="Marriott", name="Free Night Award",
        source="test",
    ))
    db.commit()
    assert use_certificate(db, cid)
    db.commit()
    certs = list_certificates(db)
    assert certs[0].used is True


# --- Spend Goal tests ---


def test_spend_goal_update(db):
    upsert_card(db, _make_card())
    gid = add_spend_goal(db, SpendGoal(
        card_id="test-card", target_cents=400000, source="test",
    ))
    db.commit()
    update_spend_goal(db, gid, 150000)
    db.commit()
    goals = list_spend_goals(db)
    assert goals[0].current_cents == 150000


# --- Status ---


def test_status(db):
    upsert_card(db, _make_card())
    upsert_benefit(db, _make_benefit(remaining_cents=5000))
    db.commit()
    status = get_status(db)
    assert status["cards"] == 1
    assert status["unused_benefits"] == 1


# --- Normalization ---


def test_normalize_name():
    assert normalize_name("Uber Cash") == "uber cash"
    assert normalize_name("  Global Entry/TSA Pre  ") == "global entrytsa pre"
    assert normalize_name("Saks Fifth Avenue") == "saks fifth avenue"
