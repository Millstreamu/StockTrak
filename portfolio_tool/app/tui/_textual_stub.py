"""Fallback implementations for a subset of Textual classes used in tests.

These lightweight shims allow the TUI application to be instantiated in
environments where the optional ``textual`` dependency is not available.
They are **not** feature complete, but they provide the small surface area the
unit tests exercise (mainly the ability to run the app and access services).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, AsyncIterator, Iterable, Sequence


class ComposeResult(list):
    """Minimal stand-in used only for typing."""


class _Styles(SimpleNamespace):
    """Very small object used to store ad-hoc style attributes."""


class Widget:
    """Base widget used to emulate the Textual API surface."""

    def __init__(
        self,
        *children: Any,
        id: str | None = None,
        classes: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.children: Iterable[Any] = children
        self.id = id
        self.classes = classes
        self.kwargs = kwargs
        self.styles = _Styles()
        self.app: "App | None" = None
        self._value: Any = None

    def focus(self) -> None:  # pragma: no cover - behaviourless stub
        """No-op focus helper."""

    def update(self, value: Any) -> None:  # pragma: no cover - behaviourless stub
        """Store a value for later inspection in tests."""

        self._value = value


class Container(Widget):
    pass


class Grid(Container):
    pass


class Static(Container):
    pass


class Header(Container):
    pass


class Footer(Container):
    pass


class TabbedContent(Container):
    pass


class TabPane(Container):
    pass


class Horizontal(Container):
    pass


class Vertical(Container):
    pass


class Button(Widget):
    def __init__(self, *children: Any, id: str | None = None, variant: str | None = None, **kwargs: Any) -> None:  # noqa: D401,E501
        super().__init__(*children, id=id, **kwargs)
        self.variant = variant


class Input(Widget):
    def __init__(self, *children: Any, placeholder: str | None = None, id: str | None = None, **kwargs: Any) -> None:  # noqa: D401,E501
        super().__init__(*children, id=id, **kwargs)
        self.placeholder = placeholder
        self.value: str = ""


class Label(Widget):
    pass


class Select(Widget):
    def __init__(self, options: Sequence[tuple[str, Any]] | None = None, *children: Any, id: str | None = None, prompt: str | None = None, **kwargs: Any) -> None:  # noqa: D401,E501
        super().__init__(*children, id=id, **kwargs)
        self.options = list(options or [])
        self.prompt = prompt
        self.value: Any = None


class DataTable(Widget):
    """Very small in-memory table supporting the methods used by tests."""

    def __init__(self, *children: Any, zebra_stripes: bool | None = None, **kwargs: Any) -> None:  # noqa: D401,E501
        super().__init__(*children, **kwargs)
        self._columns: list[dict[str, Any]] = []
        self._rows: list[tuple[list[Any], str | None]] = []
        self.cursor_type: str | None = None
        self.cursor_row: str | None = None
        self._zebra = zebra_stripes

    @property
    def columns(self) -> list[str]:
        return [column["title"] for column in self._columns]

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def add_column(self, title: str, *, key: str | None = None) -> None:
        self._columns.append({"title": title, "key": key})

    def clear(self, *, columns: bool = False) -> None:
        self._rows.clear()
        if columns:
            self._columns.clear()

    def add_row(self, *values: Any, key: str | None = None) -> None:
        self._rows.append((list(values), key))
        if key is not None:
            self.cursor_row = key

    def move_cursor(self, *, row: int = 0, column: int = 0) -> None:  # pragma: no cover - noop cursor handling
        if not self._rows:
            self.cursor_row = None
            return
        index = max(0, min(row, len(self._rows) - 1))
        _, key = self._rows[index]
        self.cursor_row = key or str(index)


class ModalScreen(Widget):
    """Placeholder that mirrors the Textual API expected in tests."""

    def __init__(self, *children: Any, **kwargs: Any) -> None:  # noqa: D401
        super().__init__(*children, **kwargs)
        self._result: Any = None

    def compose(self) -> ComposeResult:  # pragma: no cover - not used directly in tests
        return ComposeResult()

    def dismiss(self, result: Any | None = None) -> None:  # pragma: no cover - noop default
        self._result = result


class Reactive:
    """Simplistic stand-in for :func:`textual.reactive`."""

    def __init__(self, default: Any) -> None:
        self._default = default
        self._attr_name: str | None = None

    def __set_name__(self, owner: type, name: str) -> None:  # pragma: no cover - trivial
        self._attr_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None) -> Any:
        if instance is None:
            return self
        if self._attr_name is None:
            return self._default
        return getattr(instance, self._attr_name, self._default)

    def __set__(self, instance: Any, value: Any) -> None:
        if self._attr_name is None:
            raise AttributeError("Reactive descriptor misconfigured")
        setattr(instance, self._attr_name, value)


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
        self._running = False
        self._screens: list[ModalScreen] = []

    def on_mount(self) -> None:  # pragma: no cover - default no-op
        pass

    def on_unmount(self) -> None:  # pragma: no cover - default no-op
        pass

    @asynccontextmanager
    async def run_test(self) -> AsyncIterator[_TestPilot]:
        pilot = _TestPilot(self)
        self._running = True
        self.on_mount()
        try:
            yield pilot
        finally:
            self.on_unmount()
            self._running = False

    # ------------------------------------------------------------------
    def notify(self, message: str, *, severity: str = "information") -> None:  # pragma: no cover - trivial logging
        self.log(f"[{severity}] {message}")

    def log(self, message: str) -> None:  # pragma: no cover - trivial logging
        self._last_log = message

    def push_screen(self, screen: ModalScreen) -> None:  # pragma: no cover - simple storage
        screen.app = self
        self._screens.append(screen)

    async def push_screen_wait(self, screen: ModalScreen) -> Any:
        self.push_screen(screen)
        return screen._result

    def exit(self) -> None:  # pragma: no cover - trivial flag
        self._running = False
