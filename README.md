# Portfolio Tool

A command-line portfolio tracker for ASX and US equities with Australian CGT-aware lot management, price caching, and actionable reminders.

## Quickstart

```bash
# Install dependencies (preferably inside a virtual environment)
pip install -e .[dev]

# Initialise the SQLite database
default_config_dir=~/.portfolio_tool
mkdir -p "$default_config_dir"

# Add your first trade
portfolio add-trade

# View current positions
portfolio positions
```

All application data (configuration, SQLite database, and markdown exports) lives under `~/.portfolio_tool` by default. Override the location via the `PORTFOLIO_TOOL_HOME` environment variable or by passing `--config` to any command.

## Features

- Manual trade entry (buy or sell) with timezone-aware timestamps, fees, and optional notes.
- Lot tracking with FIFO, HIFO, and Specific-ID disposal matching.
- Australian CGT discount eligibility tracking per lot.
- Price fetching via Yahoo Finance APIs with SQLite-backed caching and offline fallbacks.
- Actionable alerts for CGT windows, portfolio overweight/concentration breaches, drawdowns, and stale notes.
- Rich CLI tables plus Markdown export for reports and audit logs.
- Configurable defaults using `~/.portfolio_tool/config.toml`.

## Testing

```bash
pytest
```

The test suite covers lot matching strategies, CGT discount windows, brokerage allocation, cached pricing behaviour, actionable rules, and golden-file markdown exports.

## Configuration

`portfolio config show` displays the active configuration. Update individual values with `portfolio config set KEY VALUE` (e.g. `portfolio config set price_ttl_minutes 30`). Nested keys are specified with dot notation, such as `portfolio config set target_weights.CSL 0.15`.

## Documentation

See [PRICING.md](PRICING.md) for provider and caching specifics.
