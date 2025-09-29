from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import run_portfolio


def _setup_home(monkeypatch, tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("APPDATA", raising=False)
    return home


def test_main_creates_venv_and_installs(tmp_path, monkeypatch):
    home = _setup_home(monkeypatch, tmp_path)

    venv_path = home / ".portfolio_tool" / ".venv"

    def fake_create(path: Path) -> None:
        bin_dir = path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        (bin_dir / "python").write_text("", encoding="utf-8")

    monkeypatch.setattr(run_portfolio, "create_virtualenv", fake_create)

    commands: list[list[str]] = []

    def fake_run(command, *, capture_output=False):  # noqa: ARG001
        commands.append(list(command))
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(run_portfolio, "run_command", fake_run)

    exit_code = run_portfolio.main([])
    assert exit_code == 0

    marker = venv_path / run_portfolio.MARKER_NAME
    assert marker.exists()
    requirements, _ = run_portfolio.load_requirements()
    expected_signature = run_portfolio.requirements_signature(requirements)
    assert marker.read_text(encoding="utf-8") == expected_signature

    assert commands[0][2] == "pip"
    assert commands[-1][-2:] == ["portfolio_tool", "ui"]


def test_main_skips_install_when_marker_matches(tmp_path, monkeypatch):
    home = _setup_home(monkeypatch, tmp_path)
    venv_path = home / ".portfolio_tool" / ".venv"
    bin_dir = venv_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_exe = bin_dir / "python"
    python_exe.write_text("", encoding="utf-8")

    requirements, _ = run_portfolio.load_requirements()
    signature = run_portfolio.requirements_signature(requirements)
    (venv_path / run_portfolio.MARKER_NAME).write_text(signature, encoding="utf-8")

    def fail_create(path):  # noqa: ARG001
        raise AssertionError("virtual environment should not be recreated")

    monkeypatch.setattr(run_portfolio, "create_virtualenv", fail_create)

    commands: list[list[str]] = []

    def fake_run(command, *, capture_output=False):  # noqa: ARG001
        commands.append(list(command))
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(run_portfolio, "run_command", fake_run)

    exit_code = run_portfolio.main([])
    assert exit_code == 0
    assert commands == [[str(python_exe), "-m", "portfolio_tool", "ui"]]


def test_main_runs_cli_command(tmp_path, monkeypatch):
    home = _setup_home(monkeypatch, tmp_path)
    venv_path = home / ".portfolio_tool" / ".venv"
    bin_dir = venv_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    python_exe = bin_dir / "python"
    python_exe.write_text("", encoding="utf-8")

    requirements, _ = run_portfolio.load_requirements()
    signature = run_portfolio.requirements_signature(requirements)
    (venv_path / run_portfolio.MARKER_NAME).write_text(signature, encoding="utf-8")

    commands: list[list[str]] = []

    def fake_run(command, *, capture_output=False):  # noqa: ARG001
        commands.append(list(command))
        return SimpleNamespace(stdout="", stderr="", returncode=0)

    monkeypatch.setattr(run_portfolio, "run_command", fake_run)
    monkeypatch.setattr(run_portfolio, "create_virtualenv", lambda path: None)

    exit_code = run_portfolio.main(["--cli", "positions --export md out.md"])
    assert exit_code == 0
    assert commands == [
        [
            str(python_exe),
            "-m",
            "portfolio_tool",
            "positions",
            "--export",
            "md",
            "out.md",
        ]
    ]
