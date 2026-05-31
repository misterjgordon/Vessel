.PHONY: sync test lint format help

sync:
	uv sync --extra dev

test:
	uv run --extra dev pytest tests/unit -v

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff format src tests

help:
	@echo "make sync   - install dependencies (uv sync --extra dev)"
	@echo "make test   - run unit tests"
	@echo "make lint   - ruff check + format check"
	@echo "make format - ruff format src and tests"
