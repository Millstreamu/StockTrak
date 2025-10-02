"""Toast helpers for the Textual application."""
from __future__ import annotations

from .._textual import App


def show_toast(app: App, message: str, *, severity: str = "information") -> None:
    """Display a non-blocking toast notification."""

    try:
        app.notify(message, severity=severity)
    except Exception:  # pragma: no cover - fallback for older Textual versions
        app.log(message)


__all__ = ["show_toast"]
