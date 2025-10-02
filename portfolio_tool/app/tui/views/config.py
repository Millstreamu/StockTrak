"""Configuration view."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import ast
import tomli_w

from ..widgets.forms import ConfigForm
from ..widgets.toasts import show_toast
from .base import TableView


def _flatten(prefix: str, value: Any):
    if isinstance(value, dict):
        for key, sub in sorted(value.items()):
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten(new_prefix, sub)
    else:
        yield prefix, value


class ConfigView(TableView):
    def __init__(self) -> None:
        super().__init__(
            title="Config",
            columns=[("key", "Key"), ("value", "Value")],
            key_field="key",
        )
        self._rows: list[dict[str, Any]] = []

    def on_mount(self) -> None:
        self.set_loader(self._load_page)
        super().on_mount()

    def _compute_rows(self) -> None:
        services = self.services
        if services is None:
            self._rows = []
            return
        rows: list[dict[str, Any]] = []
        for key, value in _flatten("", services.config):
            rows.append({"key": key, "value": value})
        rows.sort(key=lambda item: item["key"])
        self._rows = rows

    def _load_page(self, page: int, size: int, query: str):
        self._compute_rows()
        data = self._rows
        if query:
            q = query.upper()
            data = [row for row in data if q in row["key"].upper()]
        total = len(data)
        start = page * size
        end = start + size
        return data[start:end], total

    async def handle_edit(self) -> None:
        services = self.services
        if services is None:
            return
        selected = self.table.get_selected_row()
        if not selected:
            show_toast(self.app, "Select a config entry", severity="warning")
            return
        key = str(selected["key"])
        value = str(selected["value"])
        form = ConfigForm(key, value)
        result = await self.app.push_screen_wait(form)
        if not result:
            return
        self._update_config(result["key"], result["value"], services)
        self.refresh_view()
        show_toast(self.app, f"Updated {result['key']}", severity="success")

    def _update_config(self, key: str, value: str, services) -> None:
        parts = key.split(".") if key else []
        target = services.config
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        parsed: Any
        try:
            parsed = ast.literal_eval(value)
        except Exception:
            parsed = value
        if parts:
            target[parts[-1]] = parsed
        path: Path = services.config_path
        with path.open("wb") as fh:
            tomli_w.dump(services.config, fh)


__all__ = ["ConfigView"]
