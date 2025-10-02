"""Prices view for cached quotes."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from zoneinfo import ZoneInfo

from ..widgets.forms import ManualPriceForm
from ..widgets.toasts import show_toast
from .base import TableView


class PricesView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="Prices",
            columns=[
                ("symbol", "Symbol"),
                ("price", "Price"),
                ("asof", "As-of"),
                ("source", "Source"),
                ("stale", "Stale"),
            ],
            key_field="symbol",
        )
        self._rows: list[dict[str, Any]] = []
        self._provider = ""
        self._last_refresh: datetime | None = None

    def on_mount(self) -> None:
        self.set_loader(self._load_page)
        super().on_mount()

    def _known_symbols(self) -> list[str]:
        services = self.services
        if services is None:
            return []
        repo = services.repo
        symbols = {row["symbol"] for row in repo.list_transactions()}
        if hasattr(repo, "aggregate_open_lots"):
            symbols.update(row["symbol"] for row in repo.aggregate_open_lots())
        else:
            symbols.update({row["symbol"] for row in repo.list_lots(only_open=True)})
        return sorted(symbols)

    def _compute_rows(self) -> None:
        services = self.services
        if services is None:
            self._rows = []
            self._provider = ""
            self._last_refresh = None
            return
        pricing = services.pricing
        tz = ZoneInfo(services.config.get("timezone", "Australia/Brisbane"))
        symbols = self._known_symbols()
        quotes = pricing.get_cached(symbols)
        self._rows = []
        latest: datetime | None = None
        for symbol in symbols:
            quote = quotes.get(symbol)
            if quote:
                latest = max(latest, quote.asof) if latest else quote.asof
                self._rows.append(
                    {
                        "symbol": symbol,
                        "price": quote.price,
                        "asof": quote.asof.astimezone(tz).isoformat(),
                        "source": quote.source,
                        "stale": "yes" if quote.stale else "no",
                    }
                )
            else:
                self._rows.append(
                    {
                        "symbol": symbol,
                        "price": None,
                        "asof": "-",
                        "source": "(none)",
                        "stale": "",
                    }
                )
        self._provider = type(pricing.provider).__name__
        self._last_refresh = latest

    def _load_page(self, page: int, size: int, query: str):
        self._compute_rows()
        data = self._rows
        if query:
            q = query.upper()
            data = [row for row in data if q in str(row.get("symbol", "")).upper()]
        total = len(data)
        start = page * size
        end = start + size
        return data[start:end], total

    def status_text(self) -> str:
        last = self._last_refresh.isoformat() if self._last_refresh else "n/a"
        return f"Provider {self._provider} | Last quote {last} | {self.table.page_info()}"

    def handle_refresh(self) -> None:
        services = self.services
        if services is None:
            return
        symbols = self._known_symbols()
        quotes = services.pricing.refresh_prices(symbols or None)
        if not quotes:
            show_toast(self.app, "No quotes refreshed", severity="warning")
        else:
            show_toast(self.app, f"Refreshed {len(quotes)} quotes", severity="success")
        self.refresh_view()

    async def handle_save(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        symbol = selected.get("symbol") if selected else None
        form = ManualPriceForm(
            symbol=symbol,
            timezone=services.config.get("timezone", "Australia/Brisbane"),
        )
        result = await self.app.push_screen_wait(form)
        if not result:
            return
        services.pricing.set_manual(
            result["symbol"],
            result["price"],
            result["asof"],
        )
        show_toast(self.app, f"Manual price set for {result['symbol']}", severity="success")
        self.refresh_view()


__all__ = ["PricesView"]
