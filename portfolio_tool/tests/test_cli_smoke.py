from __future__ import annotations

import subprocess


def test_portfolio_help() -> None:
    result = subprocess.run(["portfolio", "--help"], check=True, capture_output=True, text=True)
    assert "Portfolio Tool" in result.stdout
