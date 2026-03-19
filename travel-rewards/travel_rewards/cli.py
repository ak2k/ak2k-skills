"""Click CLI entry point for travel-rewards."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from travel_rewards.db import connect, migrate
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
from travel_rewards.repository import (
    add_certificate,
    add_credit,
    add_spend_goal,
    delete_benefit,
    delete_card,
    find_benefit_by_card_and_name,
    find_card_fuzzy,
    get_benefit,
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
    update_benefit,
    update_spend_goal,
    upsert_benefit,
    upsert_card,
    use_certificate,
    use_credit,
)

console = Console()


def _to_serializable(obj: object) -> object:
    """Convert dataclasses (and lists/dicts of them) to plain dicts for JSON."""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_serializable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    return obj


def _output(ctx: click.Context, data: object, count: int | None = None) -> None:
    """Output data in JSON or human-readable format."""
    if ctx.obj["json"]:
        envelope: dict[str, object] = {"ok": True, "data": _to_serializable(data)}
        if count is not None:
            envelope["count"] = count
        click.echo(json.dumps(envelope, indent=2, default=str))
    else:
        if isinstance(data, list) and data and hasattr(data[0], "__dataclass_fields__"):
            _print_table(data)
        elif isinstance(data, dict):
            _print_dict(data)
        elif hasattr(data, "__dataclass_fields__"):
            _print_record(data)
        else:
            click.echo(data)


def _error(ctx: click.Context, message: str, suggestions: list[str] | None = None) -> None:
    """Output an error."""
    if ctx.obj["json"]:
        envelope: dict[str, object] = {"ok": False, "error": message}
        if suggestions:
            envelope["suggestions"] = suggestions
        click.echo(json.dumps(envelope, indent=2), err=True)
    else:
        console.print(f"[red]Error:[/red] {message}", stderr=True)
        if suggestions:
            console.print("[dim]Did you mean:[/dim]", stderr=True)
            for s in suggestions:
                console.print(f"  [cyan]{s}[/cyan]", stderr=True)
    sys.exit(1)


def _cents_to_dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def _print_dict(data: dict[str, object]) -> None:
    """Print a dict as a compact key-value display."""
    for k, v in data.items():
        if isinstance(v, dict):
            console.print(f"[bold]{k}:[/bold]")
            for k2, v2 in v.items():
                console.print(f"  {k2}: [cyan]{v2}[/cyan]")
        elif isinstance(v, list):
            console.print(f"[bold]{k}:[/bold] {len(v)} items")
        else:
            console.print(f"[bold]{k}:[/bold] [cyan]{v}[/cyan]")


def _print_record(obj: object) -> None:
    """Print a single dataclass as formatted key-value pairs."""
    d = asdict(obj)  # type: ignore[arg-type]
    for k, v in d.items():
        if v is not None and k not in ("normalized_name", "source", "last_updated"):
            if "cents" in k and isinstance(v, int):
                console.print(f"  [dim]{k}:[/dim] {_cents_to_dollars(v)}")
            else:
                console.print(f"  [dim]{k}:[/dim] {v}")
    console.print()


def _print_table(items: list[object]) -> None:
    """Auto-generate a Rich table from a list of dataclasses."""
    if not items:
        return
    first = items[0]

    # Choose display columns based on type
    if isinstance(first, Card):
        _print_cards_table(items)  # type: ignore[arg-type]
    elif isinstance(first, Benefit):
        _print_benefits_table(items)  # type: ignore[arg-type]
    elif isinstance(first, Balance):
        _print_balances_table(items)  # type: ignore[arg-type]
    elif isinstance(first, Credit):
        _print_credits_table(items)  # type: ignore[arg-type]
    elif isinstance(first, Certificate):
        _print_certificates_table(items)  # type: ignore[arg-type]
    elif isinstance(first, SpendGoal):
        _print_spend_goals_table(items)  # type: ignore[arg-type]
    elif isinstance(first, BenefitUsage):
        _print_usage_table(items)  # type: ignore[arg-type]
    else:
        # Fallback: generic table
        for item in items:
            _print_record(item)


def _print_cards_table(cards: list[Card]) -> None:
    table = Table(title="Cards", show_lines=False, expand=True)
    table.add_column("Name", ratio=3)
    table.add_column("Annual Fee", justify="right", style="green", ratio=1)
    table.add_column("Last 4", justify="center", ratio=1)
    table.add_column("ID", style="dim", ratio=2, no_wrap=True, overflow="ellipsis")
    for c in cards:
        table.add_row(
            c.name,
            _cents_to_dollars(c.annual_fee_cents) if c.annual_fee_cents else "-",
            c.last_four or "-",
            c.id,
        )
    console.print(table)


def _print_benefits_table(benefits: list[Benefit]) -> None:
    table = Table(title="Benefits", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Card", style="cyan", max_width=30)
    table.add_column("Benefit")
    table.add_column("Value", justify="right", style="green")
    table.add_column("Remaining", justify="right")
    table.add_column("Frequency", style="dim")
    for b in benefits:
        remaining = _cents_to_dollars(b.remaining_cents) if b.remaining_cents is not None else "-"
        remaining_style = "red" if b.remaining_cents == 0 else "green"
        table.add_row(
            str(b.id or ""),
            b.card_id,
            b.display_name,
            _cents_to_dollars(b.value_cents),
            f"[{remaining_style}]{remaining}[/{remaining_style}]",
            b.frequency.value.replace("_", " "),
        )
    console.print(table)


def _print_balances_table(balances: list[Balance]) -> None:
    table = Table(title="Loyalty Balances", show_lines=False)
    table.add_column("Program")
    table.add_column("Balance", justify="right", style="green")
    table.add_column("Unit", style="dim")
    table.add_column("Status")
    table.add_column("Updated", style="dim")
    for b in balances:
        updated = b.last_updated[:10] if b.last_updated else "-"
        table.add_row(
            b.program_name,
            f"{b.amount:,}",
            b.unit,
            b.status or "-",
            updated,
        )
    console.print(table)


def _print_credits_table(credits: list[Credit]) -> None:
    table = Table(title="Travel Credits", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Name")
    table.add_column("Remaining", justify="right", style="green")
    table.add_column("Expiration")
    table.add_column("Passenger")
    for c in credits:
        table.add_row(
            str(c.id or ""),
            c.name,
            _cents_to_dollars(c.remaining_cents),
            c.expiration or "-",
            c.passenger or "-",
        )
    console.print(table)


def _print_certificates_table(certs: list[Certificate]) -> None:
    table = Table(title="Certificates", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Program")
    table.add_column("Name")
    table.add_column("Expiration")
    table.add_column("Used", justify="center")
    for c in certs:
        used_display = "[red]Yes[/red]" if c.used else "[green]No[/green]"
        table.add_row(
            str(c.id or ""),
            c.program_name or "-",
            c.name,
            c.expiration or "-",
            used_display,
        )
    console.print(table)


def _print_spend_goals_table(goals: list[SpendGoal]) -> None:
    table = Table(title="Spend Goals", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Card", style="cyan")
    table.add_column("Progress", justify="right")
    table.add_column("Target", justify="right", style="green")
    table.add_column("Deadline")
    table.add_column("Reward")
    for g in goals:
        pct = g.current_cents / g.target_cents * 100 if g.target_cents else 0
        table.add_row(
            str(g.id or ""),
            g.card_id,
            f"{_cents_to_dollars(g.current_cents)} ({pct:.0f}%)",
            _cents_to_dollars(g.target_cents),
            g.deadline or "-",
            g.reward or "-",
        )
    console.print(table)


def _print_usage_table(usages: list[BenefitUsage]) -> None:
    table = Table(title="Usage History", show_lines=False)
    table.add_column("ID", style="dim", justify="right")
    table.add_column("Benefit ID", justify="right")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Date")
    table.add_column("Undone", justify="center")
    for u in usages:
        undone = "[yellow]Yes[/yellow]" if u.undone_at else "-"
        table.add_row(
            str(u.id or ""),
            str(u.benefit_id),
            _cents_to_dollars(u.amount_cents),
            u.used_at[:10] if u.used_at else "-",
            undone,
        )
    console.print(table)


@click.group()
@click.option("--json", "json_output", is_flag=True, help="Output as JSON")
@click.option(
    "--data-dir",
    type=click.Path(path_type=Path),
    default=Path.home() / ".config" / "travel-rewards",
    envvar="TRAVEL_REWARDS_DATA_DIR",
    help="Data directory path",
)
@click.pass_context
def cli(ctx: click.Context, json_output: bool, data_dir: Path) -> None:
    """Track travel rewards, loyalty points, and credit card benefits."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output
    ctx.obj["data_dir"] = data_dir
    ctx.obj["db"] = connect(data_dir / "rewards.db")
    migrate(ctx.obj["db"])
    ctx.call_on_close(ctx.obj["db"].close)


# --- Init ---


@cli.command()
@click.pass_context
def init(ctx: click.Context) -> None:
    """Create config directory and template card_mapping.yaml."""
    data_dir: Path = ctx.obj["data_dir"]
    data_dir.mkdir(parents=True, exist_ok=True)
    mapping = data_dir / "card_mapping.yaml"
    if not mapping.exists():
        mapping.write_text(
            "# Map AwardWallet 5-digit suffixes to card IDs\n"
            "# Example:\n"
            "# '12345': chase-sapphire-reserve-x5939\n"
        )
    _output(ctx, {"config_dir": str(data_dir), "card_mapping": str(mapping)})


# --- Import ---


@cli.group("import")
def import_group() -> None:
    """Import data from external sources."""


@import_group.command("cardpointers")
@click.option("--db-path", type=click.Path(path_type=Path), default=None,
              help="Path to CardPointers SQLite (auto-detected if omitted)")
@click.pass_context
def import_cardpointers(ctx: click.Context, db_path: Path | None) -> None:
    """Import cards and benefits from CardPointers local SQLite."""
    from travel_rewards.importers.cardpointers import DEFAULT_DB_PATH, import_cards_and_benefits

    path = db_path or DEFAULT_DB_PATH
    cards, benefits, warnings = import_cards_and_benefits(path)

    conn = ctx.obj["db"]
    cards_added = 0
    benefits_added = 0

    for card in cards:
        upsert_card(conn, card)
        cards_added += 1

    for benefit in benefits:
        upsert_benefit(conn, benefit)
        benefits_added += 1

    conn.commit()

    summary = {
        "cards_imported": cards_added,
        "benefits_imported": benefits_added,
        "warnings": warnings,
    }
    _output(ctx, summary)


@import_group.command("awardwallet")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.pass_context
def import_awardwallet(ctx: click.Context, file: Path) -> None:
    """Import balances from AwardWallet .xls export."""
    from travel_rewards.importers.awardwallet import import_accounts

    conn = ctx.obj["db"]
    data_dir: Path = ctx.obj["data_dir"]
    balances, credits, certificates, spend_goals, warnings = import_accounts(file, data_dir)

    from travel_rewards.repository import upsert_balance, upsert_certificate, upsert_credit

    balances_added = 0
    for b in balances:
        upsert_balance(conn, b)
        balances_added += 1

    conn.commit()

    summary = {
        "balances_imported": balances_added,
        "credits_imported": len(credits),
        "certificates_imported": len(certificates),
        "warnings": warnings,
    }
    _output(ctx, summary)


# --- Status ---


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Compact summary for Claude context bootstrapping."""
    _output(ctx, get_status(ctx.obj["db"]))


# --- Cards ---


@cli.group("cards", invoke_without_command=True)
@click.option("--issuer", default=None, help="Filter by issuer")
@click.pass_context
def cards_group(ctx: click.Context, issuer: str | None) -> None:
    """List or manage cards."""
    if ctx.invoked_subcommand is None:
        result = list_cards(ctx.obj["db"], issuer=issuer)
        _output(ctx, result, count=len(result))


@cards_group.command("add")
@click.option("--name", required=True)
@click.option("--issuer", default=None)
@click.option("--last-four", default=None)
@click.option("--annual-fee", type=float, default=0, help="Annual fee in dollars")
@click.option("--anniversary-month", type=int, default=None)
@click.pass_context
def cards_add(
    ctx: click.Context, name: str, issuer: str | None,
    last_four: str | None, annual_fee: float, anniversary_month: int | None,
) -> None:
    """Add a card manually."""
    from travel_rewards.importers.cardpointers import slugify_card

    card_id = slugify_card(name)
    card = Card(
        id=card_id, name=name, issuer=issuer, last_four=last_four,
        annual_fee_cents=int(annual_fee * 100),
        anniversary_month=anniversary_month, source="manual",
    )
    upsert_card(ctx.obj["db"], card)
    ctx.obj["db"].commit()
    _output(ctx, asdict(card))


@cards_group.command("edit")
@click.argument("card_id")
@click.option("--name", default=None)
@click.option("--issuer", default=None)
@click.option("--last-four", default=None)
@click.option("--annual-fee", type=float, default=None, help="Annual fee in dollars")
@click.option("--anniversary-month", type=int, default=None)
@click.pass_context
def cards_edit(
    ctx: click.Context, card_id: str, name: str | None, issuer: str | None,
    last_four: str | None, annual_fee: float | None, anniversary_month: int | None,
) -> None:
    """Edit a card field."""
    conn = ctx.obj["db"]
    card = get_card(conn, card_id)
    if card is None:
        suggestions = [c.id for c in find_card_fuzzy(conn, card_id)]
        _error(ctx, f"Card '{card_id}' not found", suggestions=suggestions)

    from travel_rewards.repository import _now

    fields: dict[str, object] = {"last_updated": _now(), "source": "manual"}
    if name is not None:
        fields["name"] = name
    if issuer is not None:
        fields["issuer"] = issuer
    if last_four is not None:
        fields["last_four"] = last_four
    if annual_fee is not None:
        fields["annual_fee_cents"] = int(annual_fee * 100)
    if anniversary_month is not None:
        fields["anniversary_month"] = anniversary_month

    cols = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [card_id]
    conn.execute(f"UPDATE cards SET {cols} WHERE card_id = ?", vals)  # noqa: S608
    conn.commit()
    _output(ctx, asdict(get_card(conn, card_id)))  # type: ignore[arg-type]


@cards_group.command("remove")
@click.argument("card_id")
@click.pass_context
def cards_remove(ctx: click.Context, card_id: str) -> None:
    """Remove a card (cascades to benefits)."""
    conn = ctx.obj["db"]
    if not delete_card(conn, card_id):
        suggestions = [c.id for c in find_card_fuzzy(conn, card_id)]
        _error(ctx, f"Card '{card_id}' not found", suggestions=suggestions)
    conn.commit()
    _output(ctx, {"deleted": card_id})


# --- Card detail ---


@cli.command("card")
@click.argument("card_id")
@click.pass_context
def card_detail(ctx: click.Context, card_id: str) -> None:
    """Show a card with its benefits."""
    conn = ctx.obj["db"]
    card = get_card(conn, card_id)
    if card is None:
        suggestions = [c.id for c in find_card_fuzzy(conn, card_id)]
        _error(ctx, f"Card '{card_id}' not found", suggestions=suggestions)
        return

    benefits = list_benefits(conn, card_id=card_id)

    if ctx.obj["json"]:
        data = {**asdict(card), "benefits": [asdict(b) for b in benefits]}
        _output(ctx, data)
    else:
        _print_record(card)
        if benefits:
            _print_benefits_table(benefits)
        else:
            console.print("  [dim]No benefits[/dim]")


# --- Benefits ---


@cli.group("benefits", invoke_without_command=True)
@click.option("--card", "card_id", default=None, help="Filter by card ID")
@click.pass_context
def benefits_group(ctx: click.Context, card_id: str | None) -> None:
    """List or manage benefits."""
    if ctx.invoked_subcommand is None:
        result = list_benefits(ctx.obj["db"], card_id=card_id)
        _output(ctx, result, count=len(result))


@benefits_group.command("add")
@click.option("--card", "card_id", required=True)
@click.option("--name", required=True)
@click.option("--value", type=float, required=True, help="Value in dollars")
@click.option("--frequency", type=click.Choice([f.value for f in BenefitFrequency]), required=True)
@click.option("--category", default=None)
@click.pass_context
def benefits_add(
    ctx: click.Context, card_id: str, name: str,
    value: float, frequency: str, category: str | None,
) -> None:
    """Add a benefit manually."""
    conn = ctx.obj["db"]
    if get_card(conn, card_id) is None:
        _error(ctx, f"Card '{card_id}' not found")

    benefit = Benefit(
        card_id=card_id, display_name=name, normalized_name=normalize_name(name),
        value_cents=int(value * 100), remaining_cents=int(value * 100),
        frequency=BenefitFrequency(frequency), category=category, source="manual",
    )
    bid = upsert_benefit(conn, benefit)
    conn.commit()
    _output(ctx, {**asdict(benefit), "id": bid})


@benefits_group.command("edit")
@click.argument("benefit_id", type=int)
@click.option("--name", default=None)
@click.option("--value", type=float, default=None, help="Value in dollars")
@click.option("--frequency", type=click.Choice([f.value for f in BenefitFrequency]), default=None)
@click.option("--category", default=None)
@click.pass_context
def benefits_edit(
    ctx: click.Context, benefit_id: int, name: str | None,
    value: float | None, frequency: str | None, category: str | None,
) -> None:
    """Edit a benefit field."""
    conn = ctx.obj["db"]
    fields: dict[str, object] = {}
    if name is not None:
        fields["display_name"] = name
    if value is not None:
        fields["value_cents"] = int(value * 100)
    if frequency is not None:
        fields["frequency"] = frequency
    if category is not None:
        fields["category"] = category

    if not update_benefit(conn, benefit_id, **fields):
        _error(ctx, f"Benefit {benefit_id} not found or nothing to update")
    conn.commit()
    _output(ctx, asdict(get_benefit(conn, benefit_id)))  # type: ignore[arg-type]


@benefits_group.command("remove")
@click.argument("benefit_id", type=int)
@click.pass_context
def benefits_remove(ctx: click.Context, benefit_id: int) -> None:
    """Remove a benefit."""
    conn = ctx.obj["db"]
    if not delete_benefit(conn, benefit_id):
        _error(ctx, f"Benefit {benefit_id} not found")
    conn.commit()
    _output(ctx, {"deleted": benefit_id})


# --- Unused ---


@cli.command("unused")
@click.option("--card", "card_id", default=None, help="Filter by card ID")
@click.pass_context
def unused(ctx: click.Context, card_id: str | None) -> None:
    """Show unused benefits."""
    result = list_unused_benefits(ctx.obj["db"], card_id=card_id)
    _output(ctx, result, count=len(result))


# --- Expiring ---


@cli.command("expiring")
@click.option("--days", type=int, default=30, help="Days to look ahead")
@click.pass_context
def expiring(ctx: click.Context, days: int) -> None:
    """Show items expiring within N days."""
    result = list_expiring(ctx.obj["db"], days=days)
    total = sum(len(v) for v in result.values())
    _output(ctx, result, count=total)


# --- Use ---


@cli.group("use", invoke_without_command=True)
@click.pass_context
def use_group(ctx: click.Context) -> None:
    """Log benefit usage or undo a usage record."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@use_group.command("log")
@click.argument("card_id")
@click.argument("benefit_name")
@click.argument("amount", type=float, required=False, default=None)
@click.pass_context
def use_log(
    ctx: click.Context, card_id: str, benefit_name: str, amount: float | None
) -> None:
    """Log benefit usage: use log <card> <benefit> [amount_dollars]."""
    conn = ctx.obj["db"]
    benefit = find_benefit_by_card_and_name(conn, card_id, benefit_name)
    if benefit is None:
        _error(ctx, f"Benefit '{benefit_name}' not found on card '{card_id}'")
        return

    amount_cents = int(amount * 100) if amount else benefit.value_cents
    usage_id = record_usage(conn, benefit.id, amount_cents)  # type: ignore[arg-type]
    conn.commit()
    _output(ctx, {"usage_id": usage_id, "benefit": benefit.display_name, "amount_cents": amount_cents})


@use_group.command("undo")
@click.argument("usage_id", type=int)
@click.pass_context
def use_undo(ctx: click.Context, usage_id: int) -> None:
    """Reverse a usage record."""
    conn = ctx.obj["db"]
    if not undo_usage(conn, usage_id):
        _error(ctx, f"Usage {usage_id} not found or already undone")
    conn.commit()
    _output(ctx, {"undone": usage_id})


# --- Usage list ---


@cli.command("usage")
@click.option("--card", "card_id", default=None, help="Filter by card ID")
@click.pass_context
def usage_list(ctx: click.Context, card_id: str | None) -> None:
    """Show usage history."""
    result = list_usage(ctx.obj["db"], card_id=card_id)
    _output(ctx, result, count=len(result))


# --- Balances ---


@cli.group("balances", invoke_without_command=True)
@click.pass_context
def balances_group(ctx: click.Context) -> None:
    """List balances."""
    if ctx.invoked_subcommand is None:
        result = list_balances(ctx.obj["db"])
        _output(ctx, result, count=len(result))


@balances_group.command("set")
@click.argument("program")
@click.argument("amount", type=int)
@click.pass_context
def balance_set(ctx: click.Context, program: str, amount: int) -> None:
    """Set a program balance manually."""
    conn = ctx.obj["db"]
    if not set_balance(conn, program, amount):
        _error(ctx, f"Program '{program}' not found")
    conn.commit()
    _output(ctx, {"program": program, "amount": amount})


# --- Credits ---


@cli.group("credits", invoke_without_command=True)
@click.pass_context
def credits_group(ctx: click.Context) -> None:
    """List active travel credits."""
    if ctx.invoked_subcommand is None:
        result = list_credits(ctx.obj["db"])
        _output(ctx, result, count=len(result))


@credits_group.command("add")
@click.option("--name", required=True)
@click.option("--issuer", default=None)
@click.option("--value", type=float, required=True, help="Value in dollars")
@click.option("--expiration", default=None)
@click.option("--passenger", default=None)
@click.option("--confirmation", default=None)
@click.pass_context
def credits_add(
    ctx: click.Context, name: str, issuer: str | None,
    value: float, expiration: str | None, passenger: str | None,
    confirmation: str | None,
) -> None:
    """Add a travel credit."""
    credit = Credit(
        name=name, issuer=issuer, value_cents=int(value * 100),
        remaining_cents=int(value * 100), expiration=expiration,
        passenger=passenger, confirmation=confirmation, source="manual",
    )
    cid = add_credit(ctx.obj["db"], credit)
    ctx.obj["db"].commit()
    _output(ctx, {**asdict(credit), "id": cid})


@credits_group.command("use")
@click.argument("credit_id", type=int)
@click.argument("amount", type=float, required=False, default=None)
@click.pass_context
def credits_use(ctx: click.Context, credit_id: int, amount: float | None) -> None:
    """Use a travel credit (decrements remaining)."""
    conn = ctx.obj["db"]
    # If no amount, use the full remaining
    if amount is None:
        row = conn.execute("SELECT remaining_cents FROM credits WHERE id = ?", (credit_id,)).fetchone()
        if row is None:
            _error(ctx, f"Credit {credit_id} not found")
            return
        amount_cents = row["remaining_cents"]
    else:
        amount_cents = int(amount * 100)

    if not use_credit(conn, credit_id, amount_cents):
        _error(ctx, f"Credit {credit_id} not found or insufficient balance")
    conn.commit()
    _output(ctx, {"used": credit_id, "amount_cents": amount_cents})


# --- Certificates ---


@cli.group("certificates", invoke_without_command=True)
@click.pass_context
def certificates_group(ctx: click.Context) -> None:
    """List certificates."""
    if ctx.invoked_subcommand is None:
        result = list_certificates(ctx.obj["db"])
        _output(ctx, result, count=len(result))


@certificates_group.command("add")
@click.option("--program", default=None)
@click.option("--name", required=True)
@click.option("--details", default=None)
@click.option("--expiration", default=None)
@click.pass_context
def certificates_add(
    ctx: click.Context, program: str | None, name: str,
    details: str | None, expiration: str | None,
) -> None:
    """Add a certificate."""
    cert = Certificate(
        program_name=program, name=name, details=details,
        expiration=expiration, source="manual",
    )
    cid = add_certificate(ctx.obj["db"], cert)
    ctx.obj["db"].commit()
    _output(ctx, {**asdict(cert), "id": cid})


@certificates_group.command("use")
@click.argument("cert_id", type=int)
@click.pass_context
def certificates_use(ctx: click.Context, cert_id: int) -> None:
    """Mark a certificate as used."""
    conn = ctx.obj["db"]
    if not use_certificate(conn, cert_id):
        _error(ctx, f"Certificate {cert_id} not found or already used")
    conn.commit()
    _output(ctx, {"used": cert_id})


# --- Spend Goals ---


@cli.group("spend-goals", invoke_without_command=True)
@click.pass_context
def spend_goals_group(ctx: click.Context) -> None:
    """List spend goals."""
    if ctx.invoked_subcommand is None:
        result = list_spend_goals(ctx.obj["db"])
        _output(ctx, result, count=len(result))


@spend_goals_group.command("add")
@click.option("--card", "card_id", required=True)
@click.option("--target", type=float, required=True, help="Target spend in dollars")
@click.option("--deadline", default=None)
@click.option("--reward", default=None, help="What you earn for hitting the target")
@click.pass_context
def spend_goals_add(
    ctx: click.Context, card_id: str, target: float,
    deadline: str | None, reward: str | None,
) -> None:
    """Create a spend goal."""
    conn = ctx.obj["db"]
    if get_card(conn, card_id) is None:
        _error(ctx, f"Card '{card_id}' not found")

    goal = SpendGoal(
        card_id=card_id, target_cents=int(target * 100),
        deadline=deadline, reward=reward, source="manual",
    )
    gid = add_spend_goal(conn, goal)
    conn.commit()
    _output(ctx, {**asdict(goal), "id": gid})


@spend_goals_group.command("update")
@click.argument("goal_id", type=int)
@click.argument("amount", type=float)
@click.pass_context
def spend_goals_update(ctx: click.Context, goal_id: int, amount: float) -> None:
    """Record incremental spend toward a goal."""
    conn = ctx.obj["db"]
    if not update_spend_goal(conn, goal_id, int(amount * 100)):
        _error(ctx, f"Spend goal {goal_id} not found")
    conn.commit()
    _output(ctx, {"updated": goal_id, "added_cents": int(amount * 100)})


# --- Config ---


@cli.command("config")
@click.pass_context
def config_path(ctx: click.Context) -> None:
    """Print config directory path."""
    _output(ctx, {"config_dir": str(ctx.obj["data_dir"])})


@cli.command("tui")
@click.pass_context
def tui(ctx: click.Context) -> None:
    """Launch interactive TUI browser."""
    from travel_rewards.tui import TravelRewardsApp

    ctx.obj["db"].close()  # TUI opens its own connection
    app = TravelRewardsApp(ctx.obj["data_dir"])
    app.run()
