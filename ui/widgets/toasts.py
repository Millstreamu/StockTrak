from __future__ import annotations

from typing import Any

from rich.console import RenderableType
from rich.panel import Panel
from textual.timer import Timer
from textual.widget import Widget


class ToastManager(Widget):
    def __init__(self) -> None:
        super().__init__(id="toasts")
        self._messages: list[RenderableType] = []
        self._dismiss_timer: Timer | None = None

    def _show(self, message: RenderableType) -> None:
        """Display a toast message for a short period before clearing it.

        The footer contains keyboard shortcuts (1–5) and can easily be
        obscured by lingering toasts. To avoid covering important UI hints or
        freshly added rows, automatically dismiss the latest toast after a
        brief delay.
        """

        self._messages.append(message)
        self.refresh()

        if self._dismiss_timer is not None:
            self._dismiss_timer.stop()
        self._dismiss_timer = self.set_timer(3, self._clear)

    def _clear(self) -> None:
        self._messages.clear()
        self.refresh()

    def success(self, message: Any) -> None:
        self._show(Panel(str(message), title="Success", border_style="green"))

    def info(self, message: Any) -> None:
        self._show(Panel(str(message), title="Info", border_style="blue"))

    def warning(self, message: Any) -> None:
        self._show(Panel(str(message), title="Warning", border_style="yellow"))

    def error(self, message: Any) -> None:
        self._show(Panel(str(message), title="Error", border_style="red"))

    def render(self) -> RenderableType:
        if not self._messages:
            return Panel("", border_style="black", height=1)
        message = self._messages[-1]
        return message
