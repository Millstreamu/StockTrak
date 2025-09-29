from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from textual.widget import Widget


class Sidebar(Widget):
    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._active = "dashboard"

    def highlight(self, key: str) -> None:
        self._active = key
        self.refresh()

    def render(self) -> Panel:
        table = Table.grid(padding=0)
        table.add_column(justify="left")
        nav_items = {
            "dashboard": "1 Dashboard",
            "positions": "2 Positions",
            "lots": "3 Lots",
            "cgt": "4 CGT Calendar",
            "actionables": "5 Actionables",
        }
        for key, label in nav_items.items():
            style = "bold cyan" if key == self._active else "white"
            table.add_row(f"[{style}]{label}[/]")
        table.add_row("")
        table.add_row("T Add Trade")
        table.add_row("R Refresh Prices")
        table.add_row("? Help")
        return Panel(table, title="Navigation", border_style="blue")
