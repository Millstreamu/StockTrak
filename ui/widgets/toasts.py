from __future__ import annotations

from typing import Any

from rich.console import RenderableType
from rich.panel import Panel
from textual.widget import Widget


class ToastManager(Widget):
    def __init__(self) -> None:
        super().__init__(id="toasts")
        self._messages: list[RenderableType] = []

    def success(self, message: Any) -> None:
        self._messages.append(Panel(str(message), title="Success", border_style="green"))
        self.refresh()

    def info(self, message: Any) -> None:
        self._messages.append(Panel(str(message), title="Info", border_style="blue"))
        self.refresh()

    def warning(self, message: Any) -> None:
        self._messages.append(Panel(str(message), title="Warning", border_style="yellow"))
        self.refresh()

    def error(self, message: Any) -> None:
        self._messages.append(Panel(str(message), title="Error", border_style="red"))
        self.refresh()

    def render(self) -> RenderableType:
        if not self._messages:
            return Panel("", border_style="black", height=1)
        message = self._messages[-1]
        return message
