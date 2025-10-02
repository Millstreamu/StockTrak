#!/bin/sh
set -eu
PYTHON=${PYTHON:-python}
exec "$PYTHON" -m portfolio_tool.app.tui.app "$@"
