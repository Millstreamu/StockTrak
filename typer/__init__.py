"""A lightweight stub of the :mod:`typer` package used for testing.

This stub provides just enough functionality for the project tests to run in
minimal environments where the real Typer dependency is not installed.  It is
*not* a drop-in replacement for the real library; it only implements the subset
of behaviour that the project relies on during the tests.  The implementation is
simple and intentionally conservative to avoid surprising behaviour when the
full Typer package is available.
"""

from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional

__all__ = [
    "Typer",
    "Context",
    "Option",
    "Argument",
    "BadParameter",
    "Abort",
    "Exit",
    "prompt",
]


class BadParameter(ValueError):
    """Exception raised when command parameters are invalid."""


class Abort(RuntimeError):
    """Exception used to signal a command abort."""


class Exit(SystemExit):
    """Exception used to exit from a command with a specific code."""


@dataclass
class _ParameterInfo:
    default: Any
    param_decls: tuple[Any, ...]
    kwargs: Dict[str, Any]


def Option(default: Any = None, *param_decls: Any, **kwargs: Any) -> _ParameterInfo:
    """Return a lightweight descriptor for command options.

    The stub only cares about the default value so that functions can be called
    directly.  Metadata such as parameter names is preserved for completeness,
    but unused.
    """

    return _ParameterInfo(default=default, param_decls=tuple(param_decls), kwargs=dict(kwargs))


def Argument(default: Any = None, *param_decls: Any, **kwargs: Any) -> _ParameterInfo:
    """Return a lightweight descriptor for command arguments."""

    return _ParameterInfo(default=default, param_decls=tuple(param_decls), kwargs=dict(kwargs))


def prompt(text: str, default: Optional[str] = None) -> str:
    """Prompt the user for input.

    The implementation simply mirrors :func:`input`.  When a default value is
    provided, it is shown alongside the prompt and returned if the user submits
    an empty string.
    """

    prompt_text = f"{text} [{default}]" if default is not None else text
    value = input(f"{prompt_text}: ")
    if not value and default is not None:
        return default
    return value


class Context:
    """Minimal command context with an ``obj`` dictionary."""

    def __init__(self) -> None:
        self.obj: Dict[str, Any] = {}


class Typer:
    """Extremely small subset of :class:`typer.Typer`.

    The class keeps track of registered commands and an optional callback.  It
    supports the ``add_typer`` method for registering sub-commands and can be
    invoked either directly via :meth:`_invoke` or by calling the instance.
    """

    def __init__(self, *, help: Optional[str] = None) -> None:
        self.help = help
        self._callback: Optional[Callable[..., Any]] = None
        self._commands: Dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------
    def command(self, name: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            command_name = name or func.__name__
            self._commands[_normalise_name(command_name)] = func
            return func

        return decorator

    def callback(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._callback = func
            return func

        return decorator

    def add_typer(self, typer_app: "Typer", name: str) -> None:
        self._commands[_normalise_name(name)] = typer_app

    # ------------------------------------------------------------------
    # Invocation helpers
    # ------------------------------------------------------------------
    def __call__(self, args: Optional[Iterable[str]] = None) -> int:
        argv = list(args) if args is not None else sys.argv[1:]
        return self._invoke(argv)

    def _invoke(self, argv: List[str]) -> int:
        ctx = Context()
        # Run the registered callback before handling commands.  The callback
        # receives the context plus default values for the parameters.
        if self._callback is not None:
            self._call_with_defaults(self._callback, ctx, [])
        return self._dispatch(ctx, argv)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _dispatch(self, ctx: Context, argv: List[str]) -> int:
        if not argv:
            return 0
        command_name, *rest = argv
        command = self._commands.get(_normalise_name(command_name))
        if command is None:
            raise BadParameter(f"Unknown command: {command_name}")
        if isinstance(command, Typer):
            # Reuse the same context when delegating to sub-apps.
            return command._invoke(rest)
        self._call_with_defaults(command, ctx, rest)
        return 0

    def _call_with_defaults(self, func: Callable[..., Any], ctx: Context, args: List[str]) -> Any:
        signature = inspect.signature(func)
        bound_args = []
        remaining_args = list(args)
        for index, parameter in enumerate(signature.parameters.values()):
            if index == 0:
                bound_args.append(ctx)
                continue
            if remaining_args:
                bound_args.append(remaining_args.pop(0))
                continue
            default = parameter.default
            if isinstance(default, _ParameterInfo):
                bound_args.append(default.default)
            elif default is inspect._empty:
                raise BadParameter(f"Missing required argument: {parameter.name}")
            else:
                bound_args.append(default)
        return func(*bound_args)


def _normalise_name(name: str) -> str:
    return name.replace("_", "-")
