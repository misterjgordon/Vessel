#!/bin/sh
# Wait for Postgres (compose healthcheck), migrate, then serve Dash.
set -e
cd /app
uv run alembic upgrade head
exec uv run python -m app.main
