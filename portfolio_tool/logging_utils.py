from __future__ import annotations

import atexit
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Optional

LOG_DIR = Path.home() / ".portfolio_tool" / "logs"
UI_LOG_PATH = LOG_DIR / "ui.txt"

_UI_LOGGER = logging.getLogger("ui")
_SESSION_LOG_PATH: Path | None = None
_SHUTDOWN_REGISTERED = False


def configure_logging() -> None:
    """Ensure log handlers are configured for UI and API tracing."""

    global _SESSION_LOG_PATH

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    if not _UI_LOGGER.handlers:
        ui_handler = logging.FileHandler(UI_LOG_PATH, encoding="utf-8")
        ui_handler.setLevel(logging.DEBUG)
        ui_handler.setFormatter(formatter)
        _UI_LOGGER.addHandler(ui_handler)

        if os.environ.get("TEXTUAL_LOG", "").lower() == "debug":
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.DEBUG)
            stream_handler.setFormatter(formatter)
            _UI_LOGGER.addHandler(stream_handler)

        _UI_LOGGER.setLevel(logging.DEBUG)
        _UI_LOGGER.propagate = False

    if _SESSION_LOG_PATH is None:
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        _SESSION_LOG_PATH = LOG_DIR / f"api-session-{timestamp}.txt"
        session_handler = logging.FileHandler(_SESSION_LOG_PATH, encoding="utf-8")
        session_handler.setLevel(logging.DEBUG)
        session_handler.setFormatter(formatter)

        api_logger = logging.getLogger("portfolio_tool")
        api_logger.setLevel(logging.DEBUG)
        api_logger.addHandler(session_handler)
        api_logger.propagate = False

        os.environ["PORTFOLIO_TOOL_API_LOG"] = str(_SESSION_LOG_PATH)
        _UI_LOGGER.info("API session log initialised at %s", _SESSION_LOG_PATH)

    global _SHUTDOWN_REGISTERED
    if not _SHUTDOWN_REGISTERED:
        atexit.register(logging.shutdown)
        _SHUTDOWN_REGISTERED = True


def get_api_log_path() -> Optional[Path]:
    """Return the current API trace log path if available."""

    if "PORTFOLIO_TOOL_API_LOG" in os.environ:
        return Path(os.environ["PORTFOLIO_TOOL_API_LOG"])
    return _SESSION_LOG_PATH


__all__ = ["LOG_DIR", "UI_LOG_PATH", "configure_logging", "get_api_log_path"]
