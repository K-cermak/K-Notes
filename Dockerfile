# syntax=docker/dockerfile:1

FROM node:26-slim AS frontend
WORKDIR /app/frontend
RUN npm install -g pnpm@12.21.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY branding.json /app/
COPY frontend/ ./
RUN pnpm exec vite build

FROM python:3.14-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    APP_DATA_DIR=/data
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
# The backend finds branding.json and the built frontend relative to itself, as in the repository.
COPY branding.json /app/
COPY --from=frontend /app/frontend/dist /app/frontend/dist

RUN useradd --uid 1000 --user-group --no-create-home --shell /usr/sbin/nologin app \
    && mkdir /data && chown app:app /data
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"]
CMD ["python", "-m", "app"]
