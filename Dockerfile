# AgentCI dashboard on Cloud Run: serves the recorded run reports + the approve action, AND runs
# the investigator LIVE on demand. Live investigation launches the Phoenix MCP server as an
# `npx @arizeai/phoenix-mcp` subprocess, so the image needs Node.js on PATH alongside Python.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Node.js (for the npx-launched Phoenix MCP server used by the live investigator).
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
# CWD must stay /app: the server reads runs/ relative to it.
CMD exec uvicorn agentci.server.app:app --host 0.0.0.0 --port ${PORT:-8080}
