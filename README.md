# Portfolio Tool — Terminal Edition

This project aims to build an auditable, deterministic portfolio management tool focused on Australian tax rules.

## Stage 3 Status

- Pricing subsystem introduced with pluggable providers (manual inline + Yahoo-based default) and disk-backed cache.
- CLI now exposes `portfolio prices show|refresh|set` for managing cached quotes and manual overrides.
- Configuration helpers centralised in `portfolio_tool.core.config` to share defaults across CLI/scripts.
- Existing persistence, domain services, and demo dataset tooling remain available for smoke testing and development.

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
