# AgentCI dashboard on Cloud Run: serves the recorded run reports + the approve action.
# The image bakes runs/*.json (git-ignored locally, shipped via .gcloudignore) so the hosted
# demo replays the real recorded runs — no credentials or model calls at runtime.
FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
# CWD must stay /app: the server reads runs/ relative to it.
CMD exec uvicorn agentci.server.app:app --host 0.0.0.0 --port ${PORT:-8080}
