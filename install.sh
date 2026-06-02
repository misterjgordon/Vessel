#!/usr/bin/env bash
# Install dependencies and prepare the local SQLite database.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

UV_INSTALL_URL='https://astral.sh/uv/install.sh'

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echo "uv is required but not installed, and curl was not found."
        echo "Install uv from https://docs.astral.sh/uv/getting-started/installation/"
        echo "then run ./install.sh again."
        exit 1
    fi

    echo "uv not found; installing from ${UV_INSTALL_URL} ..."
    curl -LsSf "${UV_INSTALL_URL}" | sh
    export PATH="${HOME}/.local/bin:${PATH}"

    if ! command -v uv >/dev/null 2>&1; then
        echo "uv was installed but is not on PATH."
        echo "Add ~/.local/bin to your PATH, then run ./install.sh again."
        exit 1
    fi
}

ensure_uv

echo 'Installing Python dependencies (uv sync) ...'
uv sync

echo 'Preparing database (migrations) ...'
uv run python -m vessel_valuation.db.migrate

echo
echo 'Installation complete.'
echo
echo '  ./run.sh          start the app'
echo '  make dev          same, if you use Make'
echo
echo 'Then open http://localhost:8050'
