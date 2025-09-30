"""Compatibility helpers for optional Rich dependency."""
from __future__ import annotations

from typing import Sequence

try:  # pragma: no cover - exercised implicitly when Rich is available
    from rich.console import Console as RichConsole  # type: ignore
    from rich.table import Table as RichTable  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for minimal environments
    class RichTable:  # type: ignore[override]
        """Minimal fallback table renderer when Rich is unavailable."""

        def __init__(self, title: str | None = None):
            self.title = title
            self._columns: list[str] = []
            self._rows: list[tuple[str, ...]] = []

        def add_column(self, header: str, **_: object) -> None:
            self._columns.append(str(header))

        def add_row(self, *values: object, **_: object) -> None:
            padded = tuple(str(value) for value in values)
            self._rows.append(padded)

        def _render(self) -> str:
            if not self._columns:
                return ""
            all_rows: list[Sequence[str]] = [self._columns, *self._rows]
            widths = [max(len(row[idx]) for row in all_rows) for idx in range(len(self._columns))]

            def format_row(row: Sequence[str]) -> str:
                padded = [row[idx].ljust(widths[idx]) for idx in range(len(self._columns))]
                return " | ".join(padded)

            lines: list[str] = []
            if self.title:
                lines.append(self.title)
            lines.append(format_row(self._columns))
            lines.append("-+-".join("-" * width for width in widths))
            for row in self._rows:
                lines.append(format_row(row))
            return "\n".join(lines)

    class RichConsole:  # type: ignore[override]
        """Simplified console that mirrors the subset of Rich used in tests."""

        @staticmethod
        def _strip_markup(text: str) -> str:
            return text.replace("[", "").replace("]", "")

        def print(self, *objects: object, sep: str = " ", end: str = "\n") -> None:
            rendered: list[str] = []
            for obj in objects:
                if isinstance(obj, RichTable):
                    rendered.append(obj._render())
                else:
                    rendered.append(self._strip_markup(str(obj)))
            print(sep.join(rendered), end=end)
else:  # pragma: no cover - executed when Rich is available
    RichConsole = RichConsole
    RichTable = RichTable

Console = RichConsole
Table = RichTable

__all__ = ["Console", "Table"]
