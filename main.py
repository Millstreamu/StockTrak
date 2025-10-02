"""Convenience entrypoint for the Portfolio Tool application.

This module allows the project to be launched with a single command::

    python main.py

When invoked without additional arguments the Textual TUI is launched.
Command-line arguments are forwarded to the Typer CLI so existing flows such
as ``python main.py positions`` remain available.
"""
from __future__ import annotations

import sys
from typing import Iterable, Sequence

from typer.main import get_command

from portfolio_tool.app.cli import app as portfolio_app

_cli = get_command(portfolio_app)


def _run_cli(argv: Sequence[str]) -> int:
    """Execute the Typer CLI with the provided arguments."""

    try:
        _cli.main(args=list(argv), prog_name="portfolio", standalone_mode=False)
    except SystemExit as exc:  # pragma: no cover - mirrors Typer behaviour
        return int(exc.code or 0)
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    """Launch the Portfolio Tool.

    Parameters
    ----------
    argv:
        Optional iterable of arguments (excluding the program name). When not
        supplied, :data:`sys.argv` is used. Running the launcher without
        arguments defaults to the TUI for a streamlined experience.
    """

    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        args = ["tui"]
    return _run_cli(args)


if __name__ == "__main__":  # pragma: no cover - manual invocation hook
    raise SystemExit(main())
