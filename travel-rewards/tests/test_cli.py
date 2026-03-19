"""Tests for CLI commands."""

import json


def test_init(invoke):
    result = invoke("init")
    assert result.exit_code == 0


def test_status_json(invoke_json):
    result = invoke_json("status")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert "cards" in data["data"]


def test_cards_empty(invoke_json):
    result = invoke_json("cards")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True
    assert data["count"] == 0


def test_cards_add_and_list(invoke_json):
    result = invoke_json("cards", "add", "--name", "Test Card", "--issuer", "Chase")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True

    result = invoke_json("cards")
    data = json.loads(result.output)
    assert data["count"] == 1


def test_card_not_found(invoke_json):
    result = invoke_json("card", "nonexistent")
    assert result.exit_code != 0
    # Error goes to stderr in JSON mode
    assert "nonexistent" in result.output or "not found" in (result.output + (result.stderr or "")).lower()


def test_benefits_add(invoke_json):
    # First add a card
    invoke_json("cards", "add", "--name", "Test Card", "--issuer", "Chase")

    result = invoke_json(
        "benefits", "add",
        "--card", "test-card",
        "--name", "Hotel Credit",
        "--value", "50",
        "--frequency", "calendar_year",
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True


def test_unused(invoke_json):
    invoke_json("cards", "add", "--name", "Test Card", "--issuer", "Chase")
    invoke_json(
        "benefits", "add", "--card", "test-card",
        "--name", "Hotel Credit", "--value", "50", "--frequency", "calendar_year",
    )

    result = invoke_json("unused")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] >= 1


def test_expiring(invoke_json):
    result = invoke_json("expiring", "--days", "30")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["ok"] is True


def test_balances_empty(invoke_json):
    result = invoke_json("balances")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["count"] == 0


def test_credits_empty(invoke_json):
    result = invoke_json("credits")
    assert result.exit_code == 0


def test_certificates_empty(invoke_json):
    result = invoke_json("certificates")
    assert result.exit_code == 0


def test_spend_goals_empty(invoke_json):
    result = invoke_json("spend-goals")
    assert result.exit_code == 0


def test_config_path(invoke_json):
    result = invoke_json("config")
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "config_dir" in data["data"]


def test_use_log_and_undo(invoke_json):
    # Setup
    invoke_json("cards", "add", "--name", "Test Card", "--issuer", "Chase")
    invoke_json(
        "benefits", "add", "--card", "test-card",
        "--name", "Hotel Credit", "--value", "50", "--frequency", "calendar_year",
    )

    # Log usage
    result = invoke_json("use", "log", "test-card", "hotel credit", "25")
    assert result.exit_code == 0
    data = json.loads(result.output)
    usage_id = data["data"]["usage_id"]

    # Undo
    result = invoke_json("use", "undo", str(usage_id))
    assert result.exit_code == 0


def test_credits_add_and_use(invoke_json):
    result = invoke_json(
        "credits", "add", "--name", "Delta Credit", "--value", "100"
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    credit_id = data["data"]["id"]

    result = invoke_json("credits", "use", str(credit_id), "50")
    assert result.exit_code == 0


def test_certificates_add_and_use(invoke_json):
    result = invoke_json(
        "certificates", "add", "--name", "Free Night", "--program", "Marriott"
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    cert_id = data["data"]["id"]

    result = invoke_json("certificates", "use", str(cert_id))
    assert result.exit_code == 0


def test_spend_goals_add_and_update(invoke_json):
    invoke_json("cards", "add", "--name", "Test Card", "--issuer", "Chase")

    result = invoke_json(
        "spend-goals", "add",
        "--card", "test-card", "--target", "4000", "--reward", "100k points",
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    goal_id = data["data"]["id"]

    result = invoke_json("spend-goals", "update", str(goal_id), "1500")
    assert result.exit_code == 0
