"""Fallback implementations for a subset of Textual classes used in tests.

These lightweight shims allow the TUI application to be instantiated in
environments where the optional ``textual`` dependency is not available.
They are **not** feature complete, but they provide the small surface area the
unit tests exercise (mainly the ability to run the app and access services).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterable


class ComposeResult(list):
    """Minimal stand-in used only for typing."""


class _BaseWidget:
    def __init__(self, *children: Any, **kwargs: Any) -> None:  # noqa: D401
        self.children: Iterable[Any] = children
        self.kwargs = kwargs


class Container(_BaseWidget):
    pass


class Static(_BaseWidget):
    pass


class Header(_BaseWidget):
    pass


class Footer(_BaseWidget):
    pass


class TabbedContent(_BaseWidget):
    pass


class TabPane(_BaseWidget):
    pass


class ModalScreen:
    """Placeholder that mirrors the Textual API expected in tests."""

    def compose(self) -> ComposeResult:  # pragma: no cover - not used directly in tests
        return ComposeResult()


class _TestPilot:
    """Simple async context manager returned by :meth:`App.run_test`."""

    def __init__(self, app: "App") -> None:
        self.app = app

    async def pause(self) -> None:
        """Compatibility no-op used by the tests."""


class App:
    """Reduced Textual ``App`` replacement.

    Only the bits that the test-suite interacts with are implemented: the
    constructor, ``run_test`` helper and ``on_mount``/``on_unmount`` hooks.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401
        pass

    def on_mount(self) -> None:  # pragma: no cover - default no-op
        pass

    def on_unmount(self) -> None:  # pragma: no cover - default no-op
        pass

    @asynccontextmanager
    async def run_test(self) -> AsyncIterator[_TestPilot]:
        pilot = _TestPilot(self)
        self.on_mount()
        try:
            yield pilot
        finally:
            self.on_unmount()
