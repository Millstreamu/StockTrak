from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import tomllib

DEFAULT_CONFIG_DIR = Path(os.environ.get("PORTFOLIO_TOOL_HOME", Path.home() / ".portfolio_tool"))
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"
DEFAULT_DB_PATH = DEFAULT_CONFIG_DIR / "portfolio.db"


@dataclass
class RuleThresholds:
    cgt_window_days: int = 60
    overweight_band: float = 0.02
    concentration_limit: float = 0.25
    drawdown_pct: float = 0.15
    stale_note_days: int = 90


@dataclass
class PricingConfig:
    provider_primary: str = "yfinance"
    fallbacks: list[str] = field(
        default_factory=lambda: ["yahooquery", "marketindex", "alphavantage"]
    )
    price_ttl_minutes: int = 15
    normalize_asx_suffix: bool = True
    include_marketindex: bool = False


@dataclass
class AlphaVantageConfig:
    api_key: str = ""


@dataclass
class Config:
    base_currency: str = "AUD"
    timezone: str = "Australia/Brisbane"
    lot_matching: str = "FIFO"
    brokerage_allocation: str = "BUY"
    price_provider: str = "yfinance"
    price_ttl_minutes: int = 15
    offline_mode: bool = False
    db_path: Path = DEFAULT_DB_PATH
    target_weights: Dict[str, float] = field(default_factory=dict)
    rule_thresholds: RuleThresholds = field(default_factory=RuleThresholds)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    alpha_vantage: AlphaVantageConfig = field(default_factory=AlphaVantageConfig)

    @property
    def config_dir(self) -> Path:
        return self.db_path.parent


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load_config(path: Optional[Path] = None) -> Config:
    cfg_path = path or DEFAULT_CONFIG_PATH
    data = _load_toml(cfg_path)

    cfg = Config()

    for key in (
        "base_currency",
        "timezone",
        "lot_matching",
        "brokerage_allocation",
        "price_provider",
    ):
        if key in data:
            setattr(cfg, key, data[key])

    if "price_ttl_minutes" in data:
        cfg.price_ttl_minutes = int(data["price_ttl_minutes"])
    if "offline_mode" in data:
        cfg.offline_mode = bool(data["offline_mode"])

    if "db_path" in data:
        cfg.db_path = Path(data["db_path"]).expanduser()
    else:
        cfg.db_path = DEFAULT_DB_PATH

    target_weights = data.get("target_weights", {})
    cfg.target_weights = {k.upper(): float(v) for k, v in target_weights.items()}

    rt = data.get("rule_thresholds", {})
    cfg.rule_thresholds = RuleThresholds(
        cgt_window_days=int(rt.get("cgt_window_days", cfg.rule_thresholds.cgt_window_days)),
        overweight_band=float(rt.get("overweight_band", cfg.rule_thresholds.overweight_band)),
        concentration_limit=float(
            rt.get("concentration_limit", cfg.rule_thresholds.concentration_limit)
        ),
        drawdown_pct=float(rt.get("drawdown_pct", cfg.rule_thresholds.drawdown_pct)),
        stale_note_days=int(rt.get("stale_note_days", cfg.rule_thresholds.stale_note_days)),
    )

    pricing = data.get("pricing", {})
    if pricing:
        cfg.pricing = PricingConfig(
            provider_primary=str(
                pricing.get("provider_primary", cfg.pricing.provider_primary)
            ),
            fallbacks=list(pricing.get("fallbacks", cfg.pricing.fallbacks)),
            price_ttl_minutes=int(
                pricing.get("price_ttl_minutes", cfg.pricing.price_ttl_minutes)
            ),
            normalize_asx_suffix=bool(
                pricing.get("normalize_asx_suffix", cfg.pricing.normalize_asx_suffix)
            ),
            include_marketindex=bool(
                pricing.get("include_marketindex", cfg.pricing.include_marketindex)
            ),
        )
        cfg.price_provider = cfg.pricing.provider_primary
        cfg.price_ttl_minutes = cfg.pricing.price_ttl_minutes

    alpha = data.get("alpha_vantage", {})
    if alpha:
        cfg.alpha_vantage = AlphaVantageConfig(api_key=str(alpha.get("api_key", "")))

    if not pricing:
        cfg.pricing.provider_primary = cfg.price_provider
        cfg.pricing.price_ttl_minutes = cfg.price_ttl_minutes

    return cfg


def ensure_app_dirs(cfg: Config) -> None:
    cfg.db_path.parent.mkdir(parents=True, exist_ok=True)


__all__ = [
    "Config",
    "RuleThresholds",
    "PricingConfig",
    "AlphaVantageConfig",
    "load_config",
    "ensure_app_dirs",
    "DEFAULT_DB_PATH",
    "DEFAULT_CONFIG_PATH",
]
