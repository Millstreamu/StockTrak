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

## Testing & Troubleshooting

Run tests with:

```bash
pytest -q
```

Key checks:

- Price cache query: We use `session.execute(select(...).limit(1)).scalars().first()`, which works across SQLAlchemy 1.4 and 2.0.
- If you see `AttributeError: 'Select' object has no attribute 'limit'`, check that:
  - You are importing `select` from `sqlalchemy`, not elsewhere.
  - Your SQLAlchemy version is >= 1.4.
- The test suite (`tests/test_price_status.py`) will fail early with a clear message if this problem exists.

## Configuration

`portfolio config show` displays the active configuration. Update individual values with `portfolio config set KEY VALUE` (e.g. `portfolio config set price_ttl_minutes 30`). Nested keys are specified with dot notation, such as `portfolio config set target_weights.CSL 0.15`.

## Documentation

See [PRICING.md](PRICING.md) for provider and caching specifics.


## Command reference

All commands accept `--config PATH` to point at an alternate configuration directory. Unless stated otherwise, datetime inputs
default to the configured timezone (Australia/Brisbane by default) and quantities/prices accept decimal values.

### Trade lifecycle

| Command | Description | Required inputs |
| --- | --- | --- |
| `portfolio add-trade` | Interactively capture a single buy or sell. Creates lots for buys and disposes of matching lots for sells using the configured matching method. | Prompts for side (`BUY`\|`SELL`), symbol, datetime, quantity, price, fees, optional exchange, optional note. |
| `portfolio edit-trade <id>` | Update an existing trade in place and recompute affected lots/disposals. | Trade ID to edit. Prompts for updated fields (press enter to keep current values). |
| `portfolio delete-trade <id>` | Remove a trade and rebuild dependent lots/disposals while recording an audit log entry. | Trade ID to delete (confirm when prompted). |

### Portfolio views & reports

| Command | Description | Key options |
| --- | --- | --- |
| `portfolio positions` | Display current holdings with quantity, average cost, last price, market value, unrealised P/L and portfolio weights. | `--export md PATH` to write the report to Markdown. |
| `portfolio lots <SYMBOL>` | Show remaining lot tranches, including acquisition details, cost base, quantity remaining, and CGT threshold date. | `SYMBOL` (required) to scope the view. `--export md PATH` for Markdown output. |
| `portfolio cgt-calendar` | List upcoming CGT discount eligibility dates within the configured window (default 60 days). | `--window DAYS` to override the window. `--export md PATH` for Markdown. |
| `portfolio pnl [--realised|--unrealised]` | Summarise realised and/or unrealised profit & loss over time. Defaults to both. | `--realised` or `--unrealised` to filter. `--export md PATH` for Markdown output. |
| `portfolio audit` | Inspect the audit log for trade edits/deletions and actionable completions/snoozes. | `--export md PATH` for Markdown output. |

### Prices

| Command | Description | Key options |
| --- | --- | --- |
| `portfolio price-refresh [SYMBOL ...]` | Refresh cached prices for the supplied symbols (or all held symbols when omitted). | Provide one or more `SYMBOL` values to force refresh specific tickers. |

### Actionables

| Command | Description | Key options |
| --- | --- | --- |
| `portfolio actionables` | Show outstanding to-dos, including CGT thresholds, overweight positions, concentration breaches, drawdowns, and stale notes. | `--complete ID` to mark an actionable done. `--snooze ID DAYS` to defer a reminder. |

### Configuration

| Command | Description | Key options |
| --- | --- | --- |
| `portfolio config show` | Print the active configuration merged from defaults and overrides. | `--json` to view raw JSON (if implemented). |
| `portfolio config set KEY VALUE` | Update a configuration value in `config.toml`. Supports dot notation for nested keys. | `KEY` (e.g. `target_weights.CSL`) and `VALUE` (validated according to type). |

