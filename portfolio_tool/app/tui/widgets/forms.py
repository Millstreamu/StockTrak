"""Form widgets used by the TUI."""
from __future__ import annotations

from datetime import datetime
from typing import Mapping

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select
from zoneinfo import ZoneInfo

TRADE_TYPES = [
    ("Buy", "BUY"),
    ("Sell", "SELL"),
    ("Dividend Reinvestment", "DRP"),
]


class TradeForm(ModalScreen[dict[str, object]]):
    """Modal form to add or edit a trade."""

    def __init__(
        self,
        *,
        title: str,
        timezone: str,
        initial: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__()
        self._title = title
        self._timezone = timezone
        self._initial = dict(initial or {})
        self._error_label: Label | None = None

    def compose(self) -> ComposeResult:
        grid = Grid(id="trade-form")
        grid.styles.grid_columns = "repeat(2, 1fr)"
        grid.styles.grid_rows = "auto auto auto auto auto auto auto auto auto"
        grid.styles.gap = (1, 2)
        grid.styles.padding = (1, 2)
        grid.styles.border = ("round", "blue")

        yield Label(self._title, id="form-title")
        yield Select(TRADE_TYPES, id="trade-type", prompt="Type")
        yield Input(placeholder="Symbol", id="symbol")
        yield Input(placeholder="Quantity", id="qty")
        yield Input(placeholder="Price", id="price")
        yield Input(placeholder="Fees", id="fees")
        yield Input(placeholder="When (ISO8601)", id="dt")
        yield Input(placeholder="Exchange", id="exchange")
        yield Input(placeholder="Broker Ref", id="broker_ref")
        yield Input(placeholder="Notes", id="notes")
        self._error_label = Label("", id="form-error")
        yield self._error_label
        yield Button("Save", variant="success", id="save")
        yield Button("Cancel", variant="error", id="cancel")

    def on_mount(self) -> None:
        select = self.query_one("#trade-type", Select)
        select.value = str(self._initial.get("type", "BUY"))
        for field in ["symbol", "qty", "price", "fees", "dt", "exchange", "broker_ref", "notes"]:
            widget = self.query_one(f"#{field}", Input)
            value = self._initial.get(field)
            if value is None:
                continue
            widget.value = str(value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "save":
            payload = self._gather_data()
            if payload is not None:
                self.dismiss(payload)

    def _gather_data(self) -> dict[str, object] | None:
        try:
            trade_type = str(self.query_one("#trade-type", Select).value or "").upper()
            symbol = self.query_one("#symbol", Input).value.strip().upper()
            qty = float(self.query_one("#qty", Input).value)
            price = float(self.query_one("#price", Input).value)
            fees_input = self.query_one("#fees", Input).value or "0"
            fees = float(fees_input)
            dt_raw = self.query_one("#dt", Input).value.strip()
            if not dt_raw:
                raise ValueError("Date/time is required")
            dt = datetime.fromisoformat(dt_raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(self._timezone))
            exchange = self.query_one("#exchange", Input).value.strip().upper() or None
            broker_ref = self.query_one("#broker_ref", Input).value.strip() or None
            notes = self.query_one("#notes", Input).value.strip() or None
        except Exception as exc:  # pragma: no cover - conversion errors
            if self._error_label is not None:
                self._error_label.update(f"[red]Error:[/red] {exc}")
            return None

        if trade_type not in {value for _, value in TRADE_TYPES}:
            if self._error_label is not None:
                self._error_label.update("[red]Invalid trade type[/red]")
            return None
        if not symbol:
            if self._error_label is not None:
                self._error_label.update("[red]Symbol is required[/red]")
            return None
        if qty <= 0:
            if self._error_label is not None:
                self._error_label.update("[red]Quantity must be positive[/red]")
            return None
        if price < 0:
            if self._error_label is not None:
                self._error_label.update("[red]Price cannot be negative[/red]")
            return None

        return {
            "type": trade_type,
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "fees": fees,
            "dt": dt,
            "exchange": exchange,
            "broker_ref": broker_ref,
            "notes": notes,
        }


class SnoozeForm(ModalScreen[int]):
    """Collect snooze duration for an actionable."""

    def __init__(self, *, title: str = "Snooze Actionable") -> None:
        super().__init__()
        self._title = title
        self._error: Label | None = None

    def compose(self) -> ComposeResult:
        container = Grid(id="snooze-form")
        container.styles.grid_rows = "auto auto auto"
        container.styles.padding = (1, 2)
        container.styles.gap = (1, 1)
        container.styles.border = ("round", "magenta")
        yield Label(self._title)
        yield Input(placeholder="Days", id="days")
        self._error = Label("", id="snooze-error")
        yield self._error
        yield Button("Confirm", variant="success", id="confirm")
        yield Button("Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "confirm":
            days_raw = self.query_one("#days", Input).value.strip()
            try:
                days = int(days_raw)
            except ValueError:
                if self._error is not None:
                    self._error.update("[red]Enter a whole number of days[/red]")
                return
            if days <= 0:
                if self._error is not None:
                    self._error.update("[red]Days must be positive[/red]")
                return
            self.dismiss(days)


class ManualPriceForm(ModalScreen[dict[str, object]]):
    """Collect manual price details."""

    def __init__(
        self,
        *,
        title: str = "Set Manual Price",
        symbol: str | None = None,
        timezone: str = "Australia/Brisbane",
    ) -> None:
        super().__init__()
        self._title = title
        self._symbol = symbol
        self._timezone = timezone
        self._error: Label | None = None

    def compose(self) -> ComposeResult:
        grid = Grid(id="price-form")
        grid.styles.grid_rows = "auto auto auto auto"
        grid.styles.padding = (1, 2)
        grid.styles.gap = (1, 1)
        grid.styles.border = ("round", "green")
        yield Label(self._title)
        yield Input(placeholder="Symbol", id="symbol")
        yield Input(placeholder="Price", id="price")
        yield Input(placeholder="As-of (ISO8601 optional)", id="asof")
        self._error = Label("", id="price-error")
        yield self._error
        yield Button("Save", variant="success", id="save")
        yield Button("Cancel", variant="error", id="cancel")

    def on_mount(self) -> None:
        if self._symbol:
            self.query_one("#symbol", Input).value = self._symbol

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "save":
            payload = self._gather()
            if payload:
                self.dismiss(payload)

    def _gather(self) -> dict[str, object] | None:
        symbol = self.query_one("#symbol", Input).value.strip().upper()
        price_raw = self.query_one("#price", Input).value.strip()
        asof_raw = self.query_one("#asof", Input).value.strip()
        if not symbol:
            if self._error is not None:
                self._error.update("[red]Symbol is required[/red]")
            return None
        try:
            price = float(price_raw)
        except ValueError:
            if self._error is not None:
                self._error.update("[red]Price must be numeric[/red]")
            return None
        asof: datetime | None = None
        if asof_raw:
            try:
                dt = datetime.fromisoformat(asof_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo(self._timezone))
                asof = dt
            except Exception:
                if self._error is not None:
                    self._error.update("[red]Invalid as-of timestamp[/red]")
                return None
        return {"symbol": symbol, "price": price, "asof": asof}


class ConfigForm(ModalScreen[dict[str, str]]):
    """Prompt for configuration updates."""

    def __init__(self, key: str, value: str) -> None:
        super().__init__()
        self._key = key
        self._value = value
        self._error: Label | None = None

    def compose(self) -> ComposeResult:
        grid = Grid(id="config-form")
        grid.styles.grid_rows = "auto auto auto"
        grid.styles.padding = (1, 2)
        grid.styles.gap = (1, 1)
        grid.styles.border = ("round", "yellow")
        yield Label(f"Update {self._key}")
        input_widget = Input(id="value")
        input_widget.value = self._value
        yield input_widget
        self._error = Label("", id="config-error")
        yield self._error
        yield Button("Save", variant="success", id="save")
        yield Button("Cancel", variant="error", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
            return
        if event.button.id == "save":
            value = self.query_one("#value", Input).value
            if not value:
                if self._error is not None:
                    self._error.update("[red]Value is required[/red]")
                return
            self.dismiss({"key": self._key, "value": value})


__all__ = ["TradeForm", "SnoozeForm", "ManualPriceForm", "ConfigForm"]
