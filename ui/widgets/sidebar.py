from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Button, Static


class Sidebar(Static):
    """Interactive navigation sidebar with keyboard hints."""

    active: reactive[str] = reactive("dashboard")

    def __init__(self) -> None:
        super().__init__(id="sidebar")

    def compose(self) -> ComposeResult:
        yield Static("Navigation", id="sidebar-title")
        yield Vertical(
            Button("1 Dashboard", id="nav-dashboard", classes="sidebar-button"),
            Button("2 Positions", id="nav-positions", classes="sidebar-button"),
            Button("3 Lots", id="nav-lots", classes="sidebar-button"),
            Button("4 CGT Calendar", id="nav-cgt", classes="sidebar-button"),
            Button("5 Actionables", id="nav-actionables", classes="sidebar-button"),
            id="sidebar-nav",
        )
        yield Static("T Add Trade\nR Refresh Prices\n? Help", id="sidebar-shortcuts")

    def on_mount(self) -> None:
        self.highlight(self.active)
        self.watch_active(self.active)

    def highlight(self, key: str) -> None:
        self.active = key

    def watch_active(self, active: str) -> None:
        for button in self.query(Button):
            button.set_class(button.id == f"nav-{active}", "active")
