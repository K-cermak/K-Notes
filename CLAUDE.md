# K-Notes

A self-hosted, open-source notes app with the layout and behaviour of Google Keep and the owner's own visual style: quick notes, checklists, labels, colors and images, usable on phones as an installable PWA with full offline editing. "K-Notes" is a working name and will change. It lives only in `branding.json`; never hard-code it anywhere else.

Read these before writing code:

- `docs/SPEC.md` is the product and architecture specification. It is the source of truth for behaviour, the data model and the sync protocol.
- `docs/PLAN.md` is the build order, as phases with checkboxes. Work one phase at a time, tick the boxes as items are done, and stop at the end of each phase for review.
- `docs/design/reference.css` is a stylesheet from another of the owner's products. It shows the visual style to match. Read it before any UI work; do not import it.

If the spec is silent or looks wrong, say so and propose a change to the spec before coding around it. Decisions already recorded in the spec were made deliberately with the project owner; do not replace them (for example SQLite with Postgres, or SSE with WebSocket) without asking.

## Stack

- Backend: Python, FastAPI, SQLAlchemy 2 (sync sessions), Alembic, SQLite in WAL mode. Dependencies managed with `uv`.
- Frontend: Vue 3 with `<script setup>` and TypeScript, Vite, Pinia, vue-router, Tailwind CSS, Reka UI, Dexie (IndexedDB), Tiptap, vue-i18n, vite-plugin-pwa, a typed API client generated with `openapi-typescript` and `openapi-fetch`. Package manager: `pnpm`.
- Distribution: one Docker image that serves both the API and the built frontend.
- Commands run through `just`.

Use the current stable release of each dependency and check its documentation rather than relying on remembered APIs. Pin versions through the lockfiles (`uv.lock`, `pnpm-lock.yaml`).

## Repository layout

```
branding.json        app name, short name, description, theme colour
Dockerfile
docker-compose.yml   example deployment
justfile
backend/
  alembic/
  app/
    main.py          FastAPI app factory, static file serving
    config.py        settings from APP_* environment variables
    db.py            engine, session, SQLite pragmas
    models/          SQLAlchemy models
    schemas/         Pydantic request and response models
    api/             routers (auth, sync, blobs, admin, tokens, notes)
    services/        business logic (merge.py is the single write path)
    cli.py           admin commands (reset-password, disable-totp, make-admin)
  tests/
frontend/
  src/
    api/             generated schema and typed client
    db/              Dexie schema and repositories
    sync/            outbox, sync engine, blob transfer
    stores/          Pinia stores
    components/
    views/
    locales/         en.json
  e2e/               Playwright tests
docs/                SPEC.md, PLAN.md, design/reference.css
```

## Conventions

- Everything in the repository is in English: code, comments, commit messages, docs, UI strings.
- Every user-visible string goes through vue-i18n. Only `en.json` is shipped.
- The app name appears only in `branding.json`. The backend, the frontend and the web manifest read it from there.
- Comments explain why, a workaround or a gotcha. Do not write comments that restate what the code or a name already says. Prefer fewer comments.
- All note data changes on the server go through `services/merge.py`. The sync endpoint and the REST API for tokens both call it; neither writes note tables directly.
- All note data changes in the client go through the repository functions in `src/db/`, which write the local row and the outbox entry in one Dexie transaction. Components never call the network for note data.
- Every database query for user data is scoped to the current user. A resource that belongs to someone else returns 404, not 403. Every new endpoint gets a test where user B tries to reach user A's data.
- Backend layering: routers in `app/api` stay thin, logic lives in `app/services`, routers do not query the database directly.
- Migrations: every schema change is an Alembic migration. Never edit a migration that has been committed.
- The frontend never hand-writes API types. They come from `just api-types`.
- API errors have one shape: a machine-readable code and a message.
- The look is specified in SPEC section 9 "Visual design" and shown in `docs/design/reference.css`. Colours come from the design tokens and the note palette only, corners are square, and surfaces are separated by hairlines rather than shadows.
- Backend: `ruff` for lint and format, `pyright` for types. Frontend: `eslint`, `prettier`, `vue-tsc`.
- Commits: small, one logical change each, Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Commit to the active branch, including `main`, unless told otherwise.

## Commands

Phase 0 creates these. Keep this section accurate when they change.

```
just setup            # install backend (uv) and frontend (pnpm) dependencies
just dev              # backend with reload + Vite dev server (proxies /api); data in backend/.data
just check            # everything CI runs: lint, types, unit tests for both sides
just fmt              # format and autofix both sides
just test-e2e         # build the image and run Playwright against it
just e2e              # Playwright against an already built image (used by CI)
just api-types        # regenerate frontend/src/api/schema.d.ts from the OpenAPI schema
just api-types-check  # fail if the generated API types are out of date (runs in CI)
just docker           # build the production image locally
```

Toolchain: Python 3.14 (`backend/.python-version`), Node 26 (`.node-version`), pnpm 12. The Node version matters: jsdom, used by Vitest, needs Node 22.22+ or newer. Playwright needs `pnpm exec playwright install chromium` once.

## Testing

The sync and merge logic is the riskiest part of the project and must be covered before UI is built on it: pytest for the merge rules and API, Vitest for the client outbox and sync engine, Playwright for two-client and offline scenarios. A phase is not done until its tests pass and you have run the app and exercised the feature yourself.
