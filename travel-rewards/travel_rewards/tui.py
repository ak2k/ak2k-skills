"""Interactive TUI for browsing travel rewards data."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from travel_rewards.db import connect, migrate
from travel_rewards.models import BenefitFrequency
from travel_rewards.repository import (
    get_status,
    list_balances,
    list_benefits,
    list_cards,
    list_certificates,
    list_credits,
    list_spend_goals,
    list_unused_benefits,
    list_usage,
)


def _dollars(cents: int) -> str:
    return f"${cents / 100:,.2f}"


class TravelRewardsApp(App):
    TITLE = "Travel Rewards"
    CSS = """
    DataTable {
        height: 1fr;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        background: $primary-background;
        color: $text;
        padding: 0 1;
    }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, data_dir: Path) -> None:
        super().__init__()
        self.data_dir = data_dir
        self.db = connect(data_dir / "rewards.db")
        migrate(self.db)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Cards", id="cards"):
                yield DataTable(id="cards-table")
            with TabPane("Benefits", id="benefits"):
                yield DataTable(id="benefits-table")
            with TabPane("Unused", id="unused"):
                yield DataTable(id="unused-table")
            with TabPane("Balances", id="balances"):
                yield DataTable(id="balances-table")
            with TabPane("Credits", id="credits"):
                yield DataTable(id="credits-table")
            with TabPane("Certificates", id="certs"):
                yield DataTable(id="certs-table")
            with TabPane("Spend Goals", id="goals"):
                yield DataTable(id="goals-table")
            with TabPane("Usage", id="usage"):
                yield DataTable(id="usage-table")
        yield Static("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._load_all()
        self._update_status()

    def action_refresh(self) -> None:
        self._load_all()
        self._update_status()
        self.notify("Refreshed")

    def _update_status(self) -> None:
        status = get_status(self.db)
        imports = ", ".join(
            f"{k}: {v[:10]}" for k, v in status.get("last_import", {}).items()
        )
        self.query_one("#status-bar").update(
            f" {status['cards']} cards | "
            f"{status['unused_benefits']} unused | "
            f"{status['expiring_soon']} expiring | "
            f"Last import: {imports or 'none'}"
        )

    def _load_all(self) -> None:
        self._load_cards()
        self._load_benefits()
        self._load_unused()
        self._load_balances()
        self._load_credits()
        self._load_certificates()
        self._load_goals()
        self._load_usage()

    def _load_cards(self) -> None:
        table = self.query_one("#cards-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Name", "Issuer", "Annual Fee", "Last 4", "ID")
        for c in list_cards(self.db):
            table.add_row(
                c.name,
                c.issuer or "-",
                _dollars(c.annual_fee_cents) if c.annual_fee_cents else "-",
                c.last_four or "-",
                c.id,
            )

    def _load_benefits(self) -> None:
        table = self.query_one("#benefits-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("ID", "Card", "Benefit", "Value", "Remaining", "Frequency")
        for b in list_benefits(self.db):
            remaining = _dollars(b.remaining_cents) if b.remaining_cents is not None else "-"
            table.add_row(
                str(b.id or ""),
                b.card_id,
                b.display_name,
                _dollars(b.value_cents),
                remaining,
                b.frequency.value.replace("_", " "),
            )

    def _load_unused(self) -> None:
        table = self.query_one("#unused-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Card", "Benefit", "Value", "Remaining", "Frequency")
        for b in list_unused_benefits(self.db):
            remaining = _dollars(b.remaining_cents) if b.remaining_cents is not None else "full"
            table.add_row(
                b.card_id,
                b.display_name,
                _dollars(b.value_cents),
                remaining,
                b.frequency.value.replace("_", " "),
            )

    def _load_balances(self) -> None:
        table = self.query_one("#balances-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("Program", "Balance", "Unit", "Status", "Updated")
        for b in list_balances(self.db):
            table.add_row(
                b.program_name,
                f"{b.amount:,}",
                b.unit,
                b.status or "-",
                b.last_updated[:10] if b.last_updated else "-",
            )

    def _load_credits(self) -> None:
        table = self.query_one("#credits-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("ID", "Name", "Remaining", "Expiration", "Passenger")
        for c in list_credits(self.db):
            table.add_row(
                str(c.id or ""),
                c.name,
                _dollars(c.remaining_cents),
                c.expiration or "-",
                c.passenger or "-",
            )

    def _load_certificates(self) -> None:
        table = self.query_one("#certs-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("ID", "Program", "Name", "Expiration", "Used")
        for c in list_certificates(self.db):
            table.add_row(
                str(c.id or ""),
                c.program_name or "-",
                c.name,
                c.expiration or "-",
                "Yes" if c.used else "No",
            )

    def _load_goals(self) -> None:
        table = self.query_one("#goals-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("ID", "Card", "Progress", "Target", "Deadline", "Reward")
        for g in list_spend_goals(self.db):
            pct = g.current_cents / g.target_cents * 100 if g.target_cents else 0
            table.add_row(
                str(g.id or ""),
                g.card_id,
                f"{_dollars(g.current_cents)} ({pct:.0f}%)",
                _dollars(g.target_cents),
                g.deadline or "-",
                g.reward or "-",
            )

    def _load_usage(self) -> None:
        table = self.query_one("#usage-table", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.zebra_stripes = True
        table.add_columns("ID", "Benefit ID", "Amount", "Date", "Undone")
        for u in list_usage(self.db):
            table.add_row(
                str(u.id or ""),
                str(u.benefit_id),
                _dollars(u.amount_cents),
                u.used_at[:10] if u.used_at else "-",
                "Yes" if u.undone_at else "-",
            )

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Sort by clicked column header."""
        table = event.data_table
        table.sort(event.column_key)

    def on_unmount(self) -> None:
        self.db.close()
