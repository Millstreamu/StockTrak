"""Entry point used by PyInstaller one-file builds."""

from __future__ import annotations

import sys


def main() -> None:
    from portfolio_tool.__main__ import app

    if len(sys.argv) == 1:
        sys.argv.append("ui")
    app()


if __name__ == "__main__":
    main()
