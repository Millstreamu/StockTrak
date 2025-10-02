"""Markdown renderer for portfolio reports."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping, Sequence

from datetime import datetime


def _format_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _normalise_fieldnames(rows, fieldnames):
    if fieldnames:
        return list(fieldnames)
    keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def render(rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None = None) -> str:
    materialised = list(rows)
    if not materialised:
        return ""
    headers = _normalise_fieldnames(materialised, fieldnames)
    header_line = " | ".join(headers)
    separator = " | ".join(["---"] * len(headers))
    lines = [f"| {header_line} |", f"| {separator} |"]
    for row in materialised:
        values = [
            _format_value(row.get(column))
            for column in headers
        ]
        lines.append(f"| {' | '.join(values)} |")
    return "\n".join(lines) + "\n"


def write(rows: Iterable[Mapping[str, object]], path: Path, fieldnames: Sequence[str] | None = None) -> None:
    text = render(list(rows), fieldnames)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


__all__ = ["render", "write"]
