.PHONY: sync test test-integration test-all lint format run dev docker-up docker-down docker-logs help

sync:
	uv sync --extra dev

test:
	uv run --extra dev pytest tests/unit -v

test-integration:
	uv run --extra dev pytest tests/integration -v

test-all: test test-integration

lint:
	uv run ruff check src tests app
	uv run ruff format --check src tests app

format:
	uv run ruff format src tests app

# Local Dash + file SQLite (default for active development).
DEV_DATABASE_URL=sqlite:///vessel_valuation.db

run:
	DATABASE_URL=$(DEV_DATABASE_URL) uv run python -m app.main

dev:
	DATABASE_URL=$(DEV_DATABASE_URL) uv run alembic upgrade head
	DATABASE_URL=$(DEV_DATABASE_URL) DASH_DEBUG=1 uv run python -m app.main

# Optional Postgres + containerized app (rebuild required after code changes).
docker-up:
	docker compose up --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f app

help:
	@echo "make sync              - install dependencies (uv sync --extra dev)"
	@echo "make test              - run unit tests"
	@echo "make test-integration  - run repository / DB integration tests"
	@echo "make test-all          - run unit + integration tests"
	@echo "make lint              - ruff check + format check"
	@echo "make format            - ruff format src, tests, and app"
	@echo "make dev               - local Dash + SQLite (http://localhost:8050, hot reload)"
	@echo "make run               - local Dash without running migrations first"
	@echo "make docker-up         - optional Postgres + app in Docker"
	@echo "make docker-down       - stop docker compose stack"
	@echo "make docker-logs       - follow app container logs"
