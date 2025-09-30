from __future__ import annotations

try:  # pragma: no cover - textual optional dependency
    from textual.message import Message
except ModuleNotFoundError:  # pragma: no cover - fallback for tests without textual
    class Message:  # type: ignore
        """Stub Message base so tests without Textual can import events."""

        pass


class DataChanged(Message):
    """Posted when data was added/edited/deleted and views must refresh."""

    pass
