.PHONY: sync setup install start test test-integration test-all lint format run dev help

code := src tests app

sync:
	uv sync

setup: sync

install:
	./install.sh

start: install
	$(MAKE) dev

test:
	uv run pytest tests/unit -v

test-integration:
	uv run pytest tests/integration -v

test-all: test test-integration

format: ## format Python code (autopep8, ruff fix, ty)
	@uv run autopep8 --recursive --in-place $(code)
	@uv run ruff check $(code) --select I001 --fix --quiet
	@uv run ruff check $(code) --quiet --fix
	@uv run ty check --error-on-warning

lint: ## lint/type-check only, no formatting
	@uv run ruff check --fix
	@uv run ty check

run:
	uv run python -m vessel_valuation.db.migrate
	uv run python -m app.main

dev:
	uv run python -m vessel_valuation.db.migrate
	DASH_DEBUG=1 uv run python -m app.main

help:
	@echo "make install           - ./install.sh (deps + migrate)"
	@echo "make start             - install then run app (first-time setup)"
	@echo "make sync              - install dependencies (uv sync)"
	@echo "make dev               - migrate and run Dash with hot reload"
	@echo "make run               - migrate and run Dash without hot reload"
	@echo "make test              - run unit tests"
	@echo "make test-integration  - run repository / DB integration tests"
	@echo "make test-all          - run unit + integration tests"
	@echo "make lint              - ruff check --fix + ty check"
	@echo "make format            - autopep8, ruff fix, ty check (fails on ty warnings)"
