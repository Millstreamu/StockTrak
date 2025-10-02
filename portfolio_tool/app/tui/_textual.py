"""Compat imports for Textual with fallback to local stubs."""
from __future__ import annotations

try:  # pragma: no cover - exercised indirectly in tests
    from textual.app import App, ComposeResult
    from textual.containers import Container, Grid, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.screen import ModalScreen
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        Label,
        Select,
        Static,
        TabbedContent,
        TabPane,
    )
    HAVE_TEXTUAL = True
except ModuleNotFoundError:  # pragma: no cover - textual optional
    from ._textual_stub import (  # type: ignore[assignment]
        App,
        Button,
        ComposeResult,
        Container,
        DataTable,
        Footer,
        Grid,
        Header,
        Horizontal,
        Input,
        Label,
        ModalScreen,
        Reactive as reactive,
        Select,
        Static,
        TabbedContent,
        TabPane,
        Vertical,
    )
    HAVE_TEXTUAL = False

__all__ = [
    "App",
    "Button",
    "ComposeResult",
    "Container",
    "DataTable",
    "Footer",
    "Grid",
    "Header",
    "Horizontal",
    "Input",
    "Label",
    "ModalScreen",
    "HAVE_TEXTUAL",
    "reactive",
    "Select",
    "Static",
    "TabbedContent",
    "TabPane",
    "Vertical",
]
