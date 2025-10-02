# Portfolio Tool — Terminal Edition

This project aims to build an auditable, deterministic portfolio management tool focused on Australian tax rules.

## Stage 2 Status

- Domain models and portfolio services implement lot matching, CGT slicing, and brokerage allocation helpers.
- Transactions recorded via the service automatically create lots, process disposals, and refresh open positions.
- Persistence layer implemented with interchangeable SQLite and JSON repositories.
- Automatic schema migrations (001_init) provision the required tables and indexes.
- Demo seeding script now provisions both backends with example trades and a cached price.
- Deterministic synthetic dataset generator (`scripts/gen_synth_50k.py`) for performance testing.

Run the CLI help to confirm installation:

```bash
portfolio --help
```

## Development

- Create a virtual environment: `make venv`
- Run tests: `make test`
- Generate demo data: `python scripts/seed_demo.py`
- Build synthetic datasets: `python scripts/gen_synth_50k.py`
