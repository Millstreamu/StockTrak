from __future__ import annotations

import asyncio

from portfolio_tool.app.tui.app import PortfolioApp
from portfolio_tool.core.config import DEFAULT_CONFIG_CONTENT


def test_tui_app_starts(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        DEFAULT_CONFIG_CONTENT
        + "\n[storage]\nbackend='json'\npath='portfolio.json'\n",
        encoding="utf-8",
    )
    app = PortfolioApp(config_path=config_path, data_dir=tmp_path)

    async def run() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            assert pilot.app.services is not None
            assert pilot.app.services.repo is not None

    asyncio.run(run())
