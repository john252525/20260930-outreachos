# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.5.2 /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY libs/ ./libs/
COPY services/linkedin-sender/ ./services/linkedin-sender/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package linkedin-sender --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/linkedin-sender/src:/app/libs/common/src:/app/libs/contracts/src:/app/libs/db/src:/app/libs/nats-client/src"

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/libs /app/libs
COPY --from=builder --chown=app:app /app/services/linkedin-sender /app/services/linkedin-sender

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://localhost:8000/healthz || exit 1
WORKDIR /app/services/linkedin-sender
CMD ["uvicorn", "linkedin_sender.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
