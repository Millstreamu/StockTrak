"""Seed a demo dataset for the portfolio tool."""
from __future__ import annotations

from pathlib import Path

from portfolio_tool.app.cli import ensure_config


def main() -> None:
    config_path = ensure_config()
    demo_dir = Path("data")
    demo_dir.mkdir(exist_ok=True)
    demo_file = demo_dir / "demo.txt"
    demo_file.write_text("Demo dataset placeholder. Configure repositories in later stages.\n")
    print(f"Config ensured at {config_path}")
    print(f"Demo data placeholder written to {demo_file}")


if __name__ == "__main__":
    main()
