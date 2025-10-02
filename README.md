# Portfolio Tool — Terminal Edition

This project aims to build an auditable, deterministic portfolio management tool focused on Australian tax rules.

## Stage 4 Status

- Reporting engine delivers position snapshots, lot ledgers, and CGT calendar views sourced from persisted trades.
- CSV/Markdown exporters provide deterministic audit trails including price provenance and report timestamps.
- CLI commands now include `portfolio positions`, `portfolio lots`, `portfolio cgt-calendar`, and `portfolio report daily` with optional price refresh/export flags.
- Existing pricing subsystem, configuration helpers, and data tooling remain available for smoke testing and development.

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
