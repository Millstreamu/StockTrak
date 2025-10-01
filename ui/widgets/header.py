from __future__ import annotations

import datetime as dt

from typing import TYPE_CHECKING

try:
    from rich.text import Text
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test envs
    class Text:  # type: ignore[override]
        """Fallback ``Text`` implementation used when ``rich`` is unavailable."""

        def __init__(self, text: str, style: str | None = None) -> None:
            self._text = text
            self.style = style

        @property
        def plain(self) -> str:
            return self._text

        def __str__(self) -> str:  # pragma: no cover - debugging helper
            return self._text
try:
    from textual.widget import Widget
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal test envs
    class Widget:  # type: ignore[override]
        """Fallback ``Widget`` used when ``textual`` is unavailable."""

        def __init__(self, *_, **__) -> None:
            """Accept arbitrary init args to mirror the real signature."""

        def refresh(self) -> None:  # pragma: no cover - no-op for tests
            """Provide ``refresh`` so widget logic can call it in tests."""

from portfolio_tool.config import Config

if TYPE_CHECKING:
    from ..textual_app import PriceStatus


class HeaderWidget(Widget):
    def __init__(self, cfg: Config) -> None:
        super().__init__(id="header")
        self.cfg = cfg
        from ..textual_app import PriceStatus  # Local import to avoid cycle

        default_reason = "offline_mode" if cfg.offline_mode else "no_prices"
        self._status = PriceStatus(
            asof=None,
            stale=cfg.offline_mode or default_reason != "ok",
            reason=default_reason,
        )

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
        status_message = self._format_status_message()
        if status_message:
            parts.append(status_message)
        return Text(" | ".join(parts), style="bold white")

    def _format_status_message(self) -> str:
        reason = self._status.reason
        if reason == "offline_mode":
            return "[O] Offline [offline_mode]"
        if reason == "stale":
            return "[P] Prices stale"
        if reason == "no_prices":
            return "[P] No cached prices"
        if reason == "ok":
            return "[P] Prices current ✓"
        return f"[P] Prices {reason}"
