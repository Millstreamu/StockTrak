"""CSV renderer for portfolio reports."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from datetime import datetime


def _normalise_fieldnames(rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None) -> list[str]:
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


def render(rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str] | None = None) -> str:
    materialised = list(rows)
    if not materialised:
        return ""
    headers = _normalise_fieldnames(materialised, fieldnames)
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    for row in materialised:
        writer.writerow({key: _format_value(row.get(key)) for key in headers})
    return buffer.getvalue()


def write(rows: Iterable[Mapping[str, object]], path: Path, fieldnames: Sequence[str] | None = None) -> None:
    materialised = list(rows)
    text = render(materialised, fieldnames)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


__all__ = ["render", "write"]
