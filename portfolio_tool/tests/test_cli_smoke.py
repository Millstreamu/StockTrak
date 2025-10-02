from __future__ import annotations

import importlib.util
import subprocess
import sys

import pytest


def test_portfolio_help() -> None:
    if importlib.util.find_spec("typer") is None:
        pytest.skip("typer dependency not available")
    result = subprocess.run(
        [sys.executable, "-m", "portfolio_tool.app.cli", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Portfolio Tool" in result.stdout
