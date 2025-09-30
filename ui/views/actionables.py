from __future__ import annotations

from typing import Iterable

from textual import events
from textual.message import Message
from textual.widgets import DataTable

from portfolio_tool.data import models


class ActionableAction(Message):
    def __init__(self, actionable_id: int, action: str) -> None:
        self.actionable_id = actionable_id
        self.action = action
        super().__init__()


class ActionablesView(DataTable):
    def __init__(self) -> None:
        super().__init__(cursor_type="row")
        self._rows: list[models.Actionable] = []

    def on_mount(self) -> None:
        self.add_column("ID", key="id", width=6)
        self.add_column("Type", key="type", width=16)
        self.add_column("Symbol", key="symbol", width=10)
        self.add_column("Message", key="message", width=60)
        self.add_column("Due", key="due", width=20)
        for column in self.columns.values():
            if column.key in {"id"}:
                column.align = "right"
        self.show_header = True

    def update_rows(self, rows: Iterable[models.Actionable]) -> None:
        self._rows = list(rows)
        self.clear()
        for actionable in self._rows:
            due = actionable.due_at.isoformat() if actionable.due_at else "—"
            self.add_row(
                str(actionable.id),
                actionable.type,
                actionable.symbol or "",
                actionable.message,
                due,
                key=str(actionable.id),
            )

    def on_key(self, event: events.Key) -> None:  # pragma: no cover - Textual callback
        if not self._rows:
            return
        if not self.is_valid_row_index(self.cursor_row):
            return
        row_key = self.ordered_rows[self.cursor_row].key
        if not row_key:
            return
        actionable_id = int(row_key)
        if event.key == "d":
            self.post_message(ActionableAction(actionable_id, "done"))
            event.stop()
        elif event.key == "s":
            self.post_message(ActionableAction(actionable_id, "snooze"))
            event.stop()
