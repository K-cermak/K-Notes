# Contributing

Thanks for helping. This file covers how the project is put together and what a change needs before it is merged. The development setup is in the [README](README.md#development).

## Before you start

- [docs/SPEC.md](docs/SPEC.md) is the source of truth for behaviour, the data model and the sync protocol. If a change needs the spec to say something else, change the spec in the same pull request and say why.
- Some decisions were made on purpose and are not up for casual replacement: SQLite rather than another database, Server-Sent Events rather than WebSocket, one server process, field-level merge with conflict copies rather than a CRDT. Open an issue first if you think one of them is wrong.
- Features listed as out of scope in the spec (sharing, reminders, e-mail, import and export, …) are not accepted.

## How the code is organised

- **One write path for notes on the server.** Every change to note data goes through `backend/app/services/merge.py`, whether it comes from a sync push or the REST API. Nothing else writes the note tables.
- **One write path for notes in the browser.** Components never call the network for note data. They read from IndexedDB and write through the functions in `frontend/src/db/`, which change the local row and record the change in the outbox in one transaction. The sync engine in `frontend/src/sync/` does the rest.
- **Thin routers.** Routers in `backend/app/api` validate and delegate; logic and queries live in `backend/app/services`.
- **Every query is scoped to the current user.** Someone else's resource answers 404, not 403. Each new endpoint gets a test in which a second user tries to reach the first user's data.
- **Generated API types.** The frontend never writes API types by hand. After changing an endpoint or schema, run `just api-types` and commit the result; CI fails when it is out of date.
- **Migrations.** Every schema change is a new Alembic migration. Never edit one that has been released.
- **Errors** have one shape: a machine-readable `code` and a `message`.

## Interface

- Every string a user sees goes through vue-i18n and lives in `frontend/src/locales/en.json`.
- The app name lives only in `branding.json`. Do not write it anywhere in the code.
- The look follows SPEC section 9, "Visual design": colours only from the tokens and the note palette, square corners, hairlines instead of shadows, tabular figures for numbers that read as data.
- The design lives in three plain CSS files in `frontend/src/styles/`, which need neither Vue nor Tailwind and can be copied into another project together with the Geist fonts:
  - `tokens.css`: colours for both themes, the note palette, type sizes, motion.
  - `base.css`: element defaults and the shared keyframes.
  - `ui.css`: the shared elements as `.ui-*` classes: buttons, inputs, selects, fields, checkboxes, radios, segmented choices, notices, badges, spinner, menus and popovers, dialogs, snackbar, meter, meta text.

  `main.css` adds Tailwind and the styles only this app needs. The components in `frontend/src/components/ui/` are thin Vue wrappers over the `.ui-*` classes. Before styling an element by hand, check whether `ui.css` already has it; if something new is needed in more than one place, add it there.
- Icon buttons need an accessible name, dialogs keep and return the focus, and everything works from the keyboard. `e2e/a11y.spec.ts` runs axe over the main screens in both themes; keep it passing.

## Tests

The sync and merge logic is the riskiest part, so changes there need tests at the level they touch: pytest for merge rules and endpoints, Vitest for the outbox and the sync engine, Playwright for anything involving two devices, going offline or reloading.

Before pushing, run:

```sh
just check      # lint, types and unit tests of both sides
just test-e2e   # builds the image and runs Playwright against it
```

Then run the app with `just dev` and try the change yourself, in both themes and at phone width if it touches the interface.

## Commits and pull requests

- Small commits, one logical change each.
- [Conventional Commits](https://www.conventionalcommits.org/) messages: `feat:`, `fix:`, `test:`, `docs:`, `chore:`. Say why in the body when the subject cannot.
- Code comments explain why, a workaround or a gotcha, never what the next line plainly does.
- Code, comments, commit messages and documentation are in English.

## Releasing

1. Set the new version in `backend/pyproject.toml` and `frontend/package.json`, and run `cd backend && uv lock` so the lockfile follows.
2. Commit, then tag and push: `git tag v1.2.3 && git push origin main v1.2.3`.

The release workflow runs all checks again, refuses a tag that does not match the version in `backend/pyproject.toml`, and publishes `ghcr.io/k-cermak/k-notes` for `linux/amd64` and `linux/arm64`, tagged with the version and `latest`. The GitHub release and its notes are written by hand.
