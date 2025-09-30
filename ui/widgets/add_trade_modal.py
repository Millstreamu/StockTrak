from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Callable

from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select
from zoneinfo import ZoneInfo

from portfolio_tool.config import Config
from ..events import DataChanged


@dataclass
class TradeFormState:
    side: str
    symbol: str
    datetime: dt.datetime
    qty: str
    price: str
    fees: str
    exchange: str | None
    note: str | None


class AddTradeModal(ModalScreen[None]):
    def __init__(self, cfg: Config) -> None:
        super().__init__()
        self.cfg = cfg
        self.on_submit: Callable[[dict], None] | None = None
        now = dt.datetime.now(ZoneInfo(cfg.timezone))
        self.state = TradeFormState(
            side="BUY",
            symbol="",
            datetime=now,
            qty="0",
            price="0",
            fees="0",
            exchange="",
            note="",
        )
        self.error = Label("", id="form-error")

    def compose(self):
        yield Label("Add Trade", id="modal-title")
        yield Select((("BUY", "BUY"), ("SELL", "SELL")), value=self.state.side, id="side")
        yield Input(placeholder="Symbol", id="symbol")
        yield Input(value=self.state.datetime.isoformat(), id="datetime")
        yield Input(placeholder="Quantity", id="qty")
        yield Input(placeholder="Price", id="price")
        yield Input(value="0", placeholder="Fees", id="fees")
        yield Input(placeholder="Exchange", id="exchange")
        yield Input(placeholder="Note", id="note")
        yield self.error
        yield Button("Save", id="save")
        yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss()
            return
        if event.button.id == "save":
            self.submit()

    def submit(self) -> None:
        try:
            side_widget = self.query_one("#side", Select)
            symbol_widget = self.query_one("#symbol", Input)
            dt_widget = self.query_one("#datetime", Input)
            qty_widget = self.query_one("#qty", Input)
            price_widget = self.query_one("#price", Input)
            fees_widget = self.query_one("#fees", Input)
            exchange_widget = self.query_one("#exchange", Input)
            note_widget = self.query_one("#note", Input)
        except Exception:  # pragma: no cover - defensive
            return
        symbol = symbol_widget.value.strip().upper()
        if not symbol:
            self.error.update("Symbol is required")
            return
        try:
            trade_dt = dt.datetime.fromisoformat(dt_widget.value.strip())
        except ValueError:
            self.error.update("Invalid datetime format")
            return
        if trade_dt.tzinfo is None:
            trade_dt = trade_dt.replace(tzinfo=ZoneInfo(self.cfg.timezone))
        data = {
            "side": side_widget.value or "BUY",
            "symbol": symbol,
            "datetime": trade_dt.astimezone(dt.timezone.utc),
            "qty": qty_widget.value.strip(),
            "price": price_widget.value.strip(),
            "fees": fees_widget.value.strip() or "0",
            "exchange": exchange_widget.value.strip() or None,
            "note": note_widget.value.strip() or None,
        }
        success = False
        if self.on_submit:
            try:
                success = bool(self.on_submit(data))
            except Exception as exc:  # pragma: no cover - defensive UI guard
                self.error.update(str(exc))
                return
        else:
            success = True

        if success:
            self.error.update("")
            app = self.app
            if app:
                refresh_all = getattr(app, "refresh_all", None)
                if callable(refresh_all):
                    refresh_all()
                else:
                    app.post_message(DataChanged())
                if hasattr(app, "toast"):
                    app.toast("Trade saved; refreshing…")
            self.dismiss()
