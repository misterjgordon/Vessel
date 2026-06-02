#!/usr/bin/env bash
# Run the Dash app (install first with ./install.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
    echo 'uv not found. Run ./install.sh first.'
    exit 1
fi

if [[ ! -d .venv ]]; then
    echo '.venv not found. Run ./install.sh first.'
    exit 1
fi

uv run python -m vessel_valuation.db.migrate
DASH_DEBUG=1 uv run python -m app.main
