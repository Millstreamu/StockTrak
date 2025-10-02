# Changelog

## Unreleased
- Core domain services covering lot matching (FIFO/HIFO/Specific-ID), CGT disposal slicing, and brokerage allocation utilities.
- Added data layer repositories (SQLite + JSON) with initial migrations.
- Demo seeding and deterministic synthetic dataset scripts.
- Pricing subsystem with provider plugins, CLI commands for `portfolio prices`, and configuration helpers.
- Reporting engine with CLI commands for positions, lots, and CGT calendar plus CSV/Markdown exporters and golden fixtures.
- Actionables rules engine with starter rule pack, persisted lifecycle (open/done/snooze), and CLI management commands.
- Textual TUI with dashboard, trades, positions, lots, CGT, actionables, prices, and config tabs plus modal forms and paged tables.
- Aggregated open lot summaries and performance test markers ensuring holdings snapshots stay under the 5s budget on 50k trades.

## 0.0.1 - Initial scaffolding
- Established package structure and CLI stub.
