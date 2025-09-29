from __future__ import annotations

import datetime as dt

from typing import TYPE_CHECKING

from rich.text import Text
from textual.widget import Widget

from portfolio_tool.config import Config

if TYPE_CHECKING:
    from ..textual_app import PriceStatus


class HeaderWidget(Widget):
    def __init__(self, cfg: Config) -> None:
        super().__init__(id="header")
        self.cfg = cfg
        from ..textual_app import PriceStatus  # Local import to avoid cycle

        self._status = PriceStatus(asof=None, stale=cfg.offline_mode)

    def update_status(self, status: "PriceStatus") -> None:
        self._status = status
        self.refresh()

    def render(self) -> Text:
        parts = ["Portfolio Tool", f"Base: {self.cfg.base_currency}"]
        if self._status.asof:
            timestamp = self._status.asof.astimezone(dt.timezone.utc).isoformat()
            parts.append(f"Prices: {timestamp}")
        else:
            parts.append("Prices: —")
        if self._status.stale:
            parts.append("[O] Offline")
        return Text(" | ".join(parts), style="bold white")
