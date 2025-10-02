# Portfolio Tool — Terminal Edition

This project aims to build an auditable, deterministic portfolio management tool focused on Australian tax rules.

## Stage 5 Status

- Actionables engine evaluates CGT windows, portfolio weights, concentrations, unrealised losses, stale prices, and trailing-stop coverage.
- CLI now supports `portfolio actionables` for listing, snoozing, and completing persisted follow-up items.
- Reporting exports (positions, lots, CGT calendar) continue to provide deterministic CSV/Markdown outputs with provenance fields.
- Pricing subsystem, configuration helpers, and data tooling remain available for smoke testing and development.

Run the CLI help to confirm installation:

```bash
portfolio --help
```

## Development

- Create a virtual environment: `make venv`
- Run tests: `make test`
- Generate demo data: `python scripts/seed_demo.py`
- Build synthetic datasets: `python scripts/gen_synth_50k.py`
- Manage price cache:
  - Show cached quotes: `portfolio prices show`
  - Refresh via provider: `portfolio prices refresh CSL IOZ`
  - Manually override: `portfolio prices set CSL 245.10 --asof 2024-03-15T16:00:00+10:00`
- Export reporting snapshots:
  - Positions: `portfolio positions --refresh-prices --export csv reports/positions.csv`
  - Lots ledger (single symbol): `portfolio lots CSL --export md reports/lots.md`
  - CGT calendar (60-day window): `portfolio cgt-calendar --window 60`
