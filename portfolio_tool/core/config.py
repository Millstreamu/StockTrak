"""Configuration helpers for the portfolio tool."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib

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

DEFAULT_CONFIG_PATH = Path("config.toml")


def ensure_config(path: Path | None = None) -> Path:
    """Ensure a configuration file exists at *path* and return it."""

    target = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not target.exists():
        target.write_text(DEFAULT_CONFIG_CONTENT, encoding="utf-8")
    return target


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load configuration data from ``config.toml`` as a dictionary."""

    config_path = ensure_config(path)
    with config_path.open("rb") as fh:
        return tomllib.load(fh)


__all__ = ["ensure_config", "load_config", "DEFAULT_CONFIG_PATH", "DEFAULT_CONFIG_CONTENT"]
