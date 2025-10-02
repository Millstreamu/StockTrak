# Portfolio Tool — Terminal Edition

This project aims to build an auditable, deterministic portfolio management tool focused on Australian tax rules.

## Stage 7 Status

- Aggregated lot summaries accelerate holdings snapshots to comfortably handle 50k synthetic trades within the <5s budget.
- Performance pytest marker (`-m performance`) seeds 50k open lots and asserts snapshot latency locally while remaining skipped on CI.
- Textual TUI (`portfolio tui`) retains dashboard, trades, positions, lots, CGT calendar, actionables, prices, and config tabs with paged tables.
- Keyboard shortcuts: `F1` help overlay, `Q` quit, `R` refresh, `/` search focus, `A` add, `E` edit, `D` delete, `S` save/export/manual actions.
- Trades tab supports add/edit/delete with validated forms and automatic portfolio rebuilds; price tab shows provider status, last refresh, and manual overrides.
- Actionables, pricing, and reporting services remain available for CLI flows alongside the TUI.

Run the CLI help to confirm installation:

```bash
portfolio --help
```

## Development

- Create a virtual environment: `make venv`
- Run tests: `make test`
- Generate demo data: `python scripts/seed_demo.py`
- Build synthetic datasets: `python scripts/gen_synth_50k.py`
- Run performance sweep locally: `pytest -q -m performance`
- Manage price cache:
  - Show cached quotes: `portfolio prices show`
  - Refresh via provider: `portfolio prices refresh CSL IOZ`
  - Manually override: `portfolio prices set CSL 245.10 --asof 2024-03-15T16:00:00+10:00`
- Export reporting snapshots:
  - Positions: `portfolio positions --refresh-prices --export csv reports/positions.csv`
  - Lots ledger (single symbol): `portfolio lots CSL --export md reports/lots.md`
  - CGT calendar (60-day window): `portfolio cgt-calendar --window 60`
- Launch the Textual TUI: `portfolio tui` (or `./scripts/run_tui.sh`)
