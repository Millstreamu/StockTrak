"""Testing helpers for the lightweight Typer stub."""

from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from typing import Iterable, Optional


class CliRunner:
    """Very small approximation of :class:`typer.testing.CliRunner`."""

    def invoke(self, app, args: Optional[Iterable[str]] = None):
        argv = list(args) if args is not None else []
        stdout = io.StringIO()
        stderr = io.StringIO()
        exception = None
        exit_code = 0
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                if hasattr(app, "_invoke"):
                    exit_code = app._invoke(argv)
                elif callable(app):
                    exit_code = app(argv)
                else:
                    raise TypeError("Application is not invokable")
            except SystemExit as exc:
                exit_code = exc.code or 0
            except Exception as exc:  # pragma: no cover - debugging aid
                exception = exc
                exit_code = 1
        output = stdout.getvalue()
        err_output = stderr.getvalue()
        return SimpleNamespace(
            exit_code=exit_code,
            stdout=output,
            stderr=err_output,
            output=output,
            exception=exception,
        )
