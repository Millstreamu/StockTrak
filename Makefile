.PHONY: venv test run lint

venv:
python3 -m venv .venv
. .venv/bin/activate && pip install -U pip && pip install -e .[dev]

test:
pytest -q

run:
portfolio --help

lint:
ruff . || true
