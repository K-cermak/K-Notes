set shell := ["bash", "-euo", "pipefail", "-c"]

image := env("IMAGE", "notes:dev")

# List the recipes
default:
    @just --list

# Install backend and frontend dependencies
setup:
    cd backend && uv sync
    cd frontend && pnpm install --frozen-lockfile

# Backend with reload and the Vite dev server, which proxies /api
dev:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT
    (cd backend && APP_BASE_URL=http://localhost:5173 APP_DATA_DIR=.data \
        uv run uvicorn app.main:create_app --factory --reload --port 8000) &
    (cd frontend && pnpm dev) &
    wait

# Everything CI runs: lint, types and unit tests for both sides
check: check-backend check-frontend

check-backend:
    cd backend && uv run ruff format --check .
    cd backend && uv run ruff check .
    cd backend && uv run pyright
    cd backend && uv run pytest

check-frontend:
    cd frontend && pnpm lint
    cd frontend && pnpm typecheck
    cd frontend && pnpm test

# Format both sides
fmt:
    cd backend && uv run ruff format . && uv run ruff check --fix .
    cd frontend && pnpm format

# Render the PWA icons in frontend/public from frontend/public/icon.svg
icons:
    cd frontend && node scripts/icons.ts

# Render the README screenshots in docs/screenshots from a fresh container of the built image
screenshots:
    #!/usr/bin/env bash
    set -euo pipefail
    name="notes-screenshots-$$"
    port=18200
    docker run -d --rm --name "$name" -p "127.0.0.1:$port:8000" \
        -e APP_BASE_URL="http://127.0.0.1:$port" --tmpfs /data:uid=1000 {{image}} > /dev/null
    trap 'docker stop "$name" > /dev/null' EXIT
    for _ in $(seq 1 60); do
        curl -fs "http://127.0.0.1:$port/api/v1/health" > /dev/null && break
        sleep 0.5
    done
    cd frontend && node scripts/screenshots.ts "http://127.0.0.1:$port"

# Regenerate frontend/src/api/schema.d.ts from the OpenAPI schema
api-types:
    #!/usr/bin/env bash
    set -euo pipefail
    schema="$(mktemp -t openapi.XXXXXX).json"
    trap 'rm -f "$schema"' EXIT
    (cd backend && uv run python -m app.openapi) > "$schema"
    cd frontend && pnpm exec openapi-typescript "$schema" -o src/api/schema.d.ts

# Fail if the generated API types are out of date
api-types-check: api-types
    git diff --exit-code -- frontend/src/api/schema.d.ts

# Build the production image locally
docker:
    docker build -t {{image}} .

# Build the image, then run Playwright against it
test-e2e: docker e2e

# Playwright against an already built image (CI builds it with its layer cache first)
e2e:
    #!/usr/bin/env bash
    set -euo pipefail
    name="notes-e2e-$$"
    port="${E2E_PORT:-18000}"
    # APP_BASE_URL must match the address the browser uses, because the server checks the Origin header.
    docker run -d --rm --name "$name" -p "127.0.0.1:$port:8000" \
        -e APP_BASE_URL="http://127.0.0.1:$port" --tmpfs /data:uid=1000 {{image}} > /dev/null
    trap 'docker stop "$name" > /dev/null' EXIT
    for _ in $(seq 1 60); do
        curl -fs "http://127.0.0.1:$port/api/v1/health" > /dev/null && break
        sleep 0.5
    done
    # E2E_CONTAINER lets the update test change sw.js inside the container, as a new build would.
    cd frontend && E2E_BASE_URL="http://127.0.0.1:$port" E2E_CONTAINER="$name" pnpm exec playwright test
