"""Bootstrap launcher for the portfolio tool.

This script creates (or reuses) a dedicated virtual environment, installs
the project's dependencies if required, and launches the Portfolio Tool UI
by default.  It is intended to be a single file that can be double-clicked
or executed with ``python run_portfolio.py`` on systems with Python 3.11+.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence


REPO_ROOT = Path(__file__).resolve().parent
LOCKFILE = REPO_ROOT / "requirements-lock.txt"
MARKER_NAME = ".requirements_hash"

REQUIREMENTS: Sequence[str] = (
    "typer>=0.12",
    "rich>=13",
    "textual>=0.60",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pydantic>=2.7",
    "yfinance>=0.2",
    "yahooquery>=2.3",
    "tzdata; platform_system=='Windows'",
)


class LaunchError(RuntimeError):
    """Raised when bootstrapping fails."""


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the Portfolio Tool")
    parser.add_argument(
        "--cli",
        metavar="ARGS",
        help="Run a CLI command instead of launching the UI",
    )
    parser.add_argument(
        "--reset-venv",
        action="store_true",
        help="Rebuild the virtual environment before launching",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Install the project in editable mode (for contributors)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def ensure_python_version() -> None:
    if sys.version_info < (3, 11):
        raise LaunchError(
            "Python 3.11 or newer is required. "
            "Please install a compatible version and try again."
        )


def resolve_base_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata) / "portfolio_tool"
        else:
            base = Path(os.path.expanduser("~")) / ".portfolio_tool"
    else:
        base = Path(os.path.expanduser("~")) / ".portfolio_tool"
    base.mkdir(parents=True, exist_ok=True)
    return base


def venv_path_for_platform() -> Path:
    return resolve_base_dir() / ".venv"


def get_venv_python(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def create_virtualenv(venv_path: Path) -> None:
    print("Creating virtual environment…")
    parent = venv_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    import venv

    builder = venv.EnvBuilder(with_pip=True)
    builder.create(str(venv_path))


def remove_virtualenv(venv_path: Path) -> None:
    if venv_path.exists():
        print("Removing existing virtual environment…")
        shutil.rmtree(venv_path)


def run_command(command: Sequence[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=True,
        text=True,
        capture_output=capture_output,
    )


def requirements_from_lockfile(lockfile: Path) -> List[str]:
    requirements: List[str] = []
    for line in lockfile.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirements.append(stripped)
    return requirements


def load_requirements() -> tuple[List[str], Path | None]:
    if LOCKFILE.exists():
        return requirements_from_lockfile(LOCKFILE), LOCKFILE
    return list(REQUIREMENTS), None


def requirements_signature(requirements: Iterable[str]) -> str:
    combined = "\n".join(requirements)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def pip_base_command(python_executable: Path) -> list[str]:
    return [
        str(python_executable),
        "-m",
        "pip",
        "--disable-pip-version-check",
        "--no-input",
    ]


def upgrade_pip(python_executable: Path) -> None:
    print("Upgrading pip…")
    run_command(pip_base_command(python_executable) + ["install", "--quiet", "--upgrade", "pip"])


def install_requirements(
    python_executable: Path,
    requirements: Sequence[str],
    *,
    requirement_file: Path | None,
) -> None:
    print("Installing dependencies…")
    if requirement_file is not None:
        command = pip_base_command(python_executable) + [
            "install",
            "--quiet",
            "--upgrade",
            "-r",
            str(requirement_file),
        ]
    else:
        command = (
            pip_base_command(python_executable)
            + ["install", "--quiet", "--upgrade"]
            + list(requirements)
        )
    run_command(command)


def install_editable(python_executable: Path) -> None:
    print("Installing portfolio-tool in editable mode…")
    command = pip_base_command(python_executable) + [
        "install",
        "--quiet",
        "--upgrade",
        "-e",
        str(REPO_ROOT),
    ]
    run_command(command)


def marker_path(venv_path: Path) -> Path:
    return venv_path / MARKER_NAME


def ensure_dependencies(
    python_executable: Path,
    requirements: Sequence[str],
    requirement_file: Path | None,
    *,
    venv_path: Path,
    force: bool = False,
) -> None:
    signature = requirements_signature(requirements)
    marker = marker_path(venv_path)
    need_install = force or not marker.exists() or marker.read_text(encoding="utf-8") != signature
    if need_install:
        upgrade_pip(python_executable)
        install_requirements(python_executable, requirements, requirement_file=requirement_file)
        marker.write_text(signature, encoding="utf-8")
    else:
        print("Dependencies already satisfied.")


def launch_application(python_executable: Path, cli_args: Sequence[str] | None) -> None:
    if cli_args:
        command = [str(python_executable), "-m", "portfolio_tool"] + list(cli_args)
        print("Running CLI command…")
    else:
        command = [str(python_executable), "-m", "portfolio_tool", "ui"]
        print("Launching Portfolio UI…")
    run_command(command)


def prepare_venv(reset: bool) -> tuple[Path, Path]:
    venv_path = venv_path_for_platform()
    if reset:
        remove_virtualenv(venv_path)

    python_executable = get_venv_python(venv_path)
    if not python_executable.exists():
        create_virtualenv(venv_path)
    python_executable = get_venv_python(venv_path)
    if not python_executable.exists():
        raise LaunchError("Failed to locate Python inside the virtual environment.")
    return venv_path, python_executable


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        ensure_python_version()
        venv_path, python_executable = prepare_venv(args.reset_venv)

        requirements, requirement_file = load_requirements()
        force_install = args.reset_venv or not marker_path(venv_path).exists()
        ensure_dependencies(
            python_executable,
            requirements,
            requirement_file=requirement_file,
            venv_path=venv_path,
            force=force_install,
        )

        if args.dev:
            install_editable(python_executable)

        cli_args: Sequence[str] | None
        if args.cli:
            cli_args = shlex.split(args.cli)
        else:
            cli_args = None
        launch_application(python_executable, cli_args)
        return 0
    except LaunchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "You can try running 'python -m portfolio_tool ui' from the project "
            "directory once dependencies are installed.",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError as exc:
        print("A command failed while bootstrapping the application.", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        print(
            "You can try running the reported command manually inside the "
            "virtual environment to diagnose the problem.",
            file=sys.stderr,
        )
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
