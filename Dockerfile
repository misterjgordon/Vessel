# App image for local dev (docker compose) and deploy targets.
FROM python:3.11-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app \
    PATH=/app/.venv/bin:$PATH

# Dependency layer (rebuild when lockfile changes).
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY alembic.ini ./
COPY app ./app
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8050

ENTRYPOINT ["/docker-entrypoint.sh"]
