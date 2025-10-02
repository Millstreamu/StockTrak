"""Command-line interface for the portfolio tool."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print

APP_NAME = "portfolio"
DEFAULT_CONFIG_PATH = Path.cwd() / "config.toml"
DEFAULT_CONFIG_CONTENT = """base_currency = \"AUD\"
timezone = \"Australia/Brisbane\"
lot_matching = \"FIFO\"
brokerage_allocation = \"BUY\"
[prices]
provider = \"online_default\"
cache_ttl_minutes = 15
stale_price_max_minutes = 60
exchange_suffix_map = { \"ASX\" = \".AX\" }
[target_weights]
CSL = 0.15
IOZ = 0.20
[rule_thresholds]
cgt_window_days = 60
overweight_band = 0.02
concentration_limit = 0.25
loss_threshold_pct = -0.15
"""


def ensure_config(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    """Ensure the default configuration file exists."""
    if not path.exists():
        path.write_text(DEFAULT_CONFIG_CONTENT)
    return path


# Ensure configuration is ready at import time to cover --help invocations.
ensure_config()

app = typer.Typer(help="Portfolio Tool — Terminal Edition")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> Optional[int]:
    """Application entrypoint that ensures configuration is present."""
    ensure_config()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        return 0
    return None


@app.command()
def version() -> None:
    """Print the CLI version."""
    print("portfolio-tool 0.0.1")


if __name__ == "__main__":
    sys.exit(app())
