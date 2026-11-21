FROM python:3.12-slim AS dependencies

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project

FROM python:3.12-slim

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home dataagent && install -d -o dataagent /app/data
COPY --from=dependencies /app/.venv /app/.venv
COPY app ./app
COPY migrations ./migrations
COPY resources ./resources
USER dataagent
EXPOSE 8065
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8065", "--workers", "1"]
