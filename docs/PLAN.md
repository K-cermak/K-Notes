# Build plan

Work through the phases in order. Each phase ends with working software, passing tests and a commit. Tick a box when the item is built, tested and committed. Stop after each phase and report: what was built, what was verified and how, anything that deviates from `SPEC.md`, and open questions. Do not start the next phase until the owner confirms.

The order is deliberate. Sync is built and tested before the real UI, because every UI feature depends on it and retrofitting offline behaviour onto an online app means rewriting it.

Section numbers refer to `docs/SPEC.md`.

## Phase 0: Scaffold

- [x] Initialise the git repository, `.gitignore`, MIT `LICENSE`, `branding.json`, the layout from `CLAUDE.md`.
- [x] Backend: FastAPI app factory, settings (section 3), SQLite engine with pragmas, Alembic wired to run at startup, `GET /api/v1/health` and `GET /api/v1/config`.
- [x] Frontend: Vite, Vue, TypeScript, Tailwind, vue-router, Pinia, vue-i18n with `en.json`, dev proxy for `/api`.
- [x] Design foundation from section 9 "Visual design": colour tokens with `light-dark()` exposed to Tailwind, self-hosted Geist and Geist Mono, zero radius, global icon stroke settings, and the base controls (button variants, input, checkbox, notice) on a throwaway showcase route.
- [x] Typed API client generated from the OpenAPI schema (`just api-types`).
- [x] Lint, format and type-check tooling for both sides.
- [x] `justfile` with the commands listed in `CLAUDE.md`.
- [x] Dockerfile and `docker-compose.yml`; the image serves the SPA and the API.
- [x] GitHub Actions workflow running `just check`, the API types check and the image build.

Done when: `just docker` succeeds, the container shows a placeholder page that displays the version from `/config` through the typed client, the showcase route, put next to the owner's reference form in light and in dark, reads as the same design family, and CI is green.

## Phase 1: Accounts and sessions

- [x] Users, sessions, invites, settings tables.
- [x] Setup screen that creates the admin when there are no users.
- [x] Login, logout, current user, profile settings (display name, locale, theme, default view), change password (revoking other sessions), list and revoke sessions.
- [x] Cookie sessions, origin check, login throttling, security headers (section 7).
- [x] Admin API: list users, invite links, password reset links, deactivate and reactivate, delete, granting and revoking admin rights with the last-admin and self-change guards (section 7), registration toggle.
- [x] Invite acceptance, self-registration and password reset pages.
- [x] CLI: `reset-password`, `disable-totp`, `make-admin`.
- [x] Minimal setup and login screens, enough to obtain a session.

Done when: pytest covers the flows above, including that a non-admin cannot reach admin endpoints, that the last active admin cannot be demoted, deactivated or deleted, that admins cannot demote or deactivate themselves, that an invite or reset link works once and expires, and that a deactivated user's session stops working at once and they cannot log in again; and on a fresh instance you can create the admin, invite a second user by link, log out and log in through the browser.

## Phase 2: Sync backend

- [ ] Models for all synced entities with bookkeeping columns (section 4).
- [ ] `services/merge.py` implementing sections 5.1, 5.2, 5.4 and 5.5.
- [ ] Rich text validation and plain-text extraction (section 4.1).
- [ ] Push, pull and SSE endpoints (section 5.3), with the in-process listener registry.
- [ ] Trash purge task (section 5.7), without blob cleanup for now, and the nightly cleanup of expired sessions and invites.

Done when: every merge case listed in section 12 has a pytest test, user isolation is tested, and a scripted run with two simulated devices (plain HTTP clients in a test) converges to the same state, including one conflict copy.

## Phase 3: Client data layer

- [ ] Dexie schema, repository functions, outbox with coalescing (section 5.6).
- [ ] Sync engine: cycle, triggers, backoff, SSE listener, status store, auth edge cases.
- [ ] A deliberately plain UI: a list of notes with title and plain text, create, edit, delete. Its purpose is to exercise sync, and it will be replaced.

Done when: Vitest covers the engine cases in section 12, and Playwright shows a note syncing between two contexts, an offline edit syncing after reconnect, and a conflict copy appearing.

## Phase 4: Interface for text notes

- [ ] App shell: top bar, navigation drawer, composer, responsive behaviour (section 9, Layout).
- [ ] Masonry grid composable and list view.
- [ ] Note card and editor with Tiptap and the formatting control.
- [ ] Colors, pin, archive, trash views, make a copy, undo snackbar.
- [ ] Light and dark theme from the tokens, saved in the profile and cached locally.
- [ ] Empty states and keyboard shortcuts.

Done when: the app is usable for text notes on a desktop browser and at phone width, in both themes; you have compared its layout and behaviour side by side with Google Keep and fixed the obvious differences; and its look, put next to the owner's reference form, reads as the same design family. Include screenshots in the report.

## Phase 5: Labels and search

- [ ] Label management dialog, label picker, label views in the drawer, chips on cards.
- [ ] Local search with case and diacritics folding.

Done when: label rename and delete propagate between two clients, and searching `cerny` finds a note containing `černý`.

## Phase 6: Checklists

- [ ] Checklist editor, card preview, checked section, item reordering, paste of several lines, conversion to and from text (section 9, Checklists).

Done when: two clients checking different items of the same list offline both keep their changes after sync, covered by a Playwright test.

## Phase 7: Images

- [ ] Client image processing, hashing and local blob storage (section 6).
- [ ] Blob endpoints with verification and per-user access control.
- [ ] Blob upload and download steps in the sync cycle.
- [ ] Images on cards and in the editor, viewer on click, remove image.
- [ ] "Download images on demand" setting, storage persistence request and storage use display.
- [ ] Blob cleanup after purge.

Done when: an image attached offline appears on a second device after reconnecting; a second user cannot fetch the blob by its hash; the same file attached twice is stored once.

## Phase 8: Ordering and multi-select

- [ ] Drag to reorder notes in the masonry grid and list view, with mouse and touch.
- [ ] Selection mode and bulk actions.

Done when: reordering persists across reload and syncs to a second client, dragging works on a real phone or touch emulation without triggering page scroll or text selection, and bulk archive of several notes can be undone in one action.

## Phase 9: PWA and offline polish

- [ ] Service worker, manifest from `branding.json`, icons, update snackbar, iOS install hint (section 10).
- [ ] Offline start, sync status in the top bar, unsent changes count.
- [ ] Safe-area and on-screen keyboard handling.

Done when: after one online visit the app loads with the network disabled and shows all notes and images; Lighthouse reports it as installable; a new build triggers the update snackbar and does not reload by itself.

## Phase 10: TOTP, OIDC and API tokens

- [ ] TOTP enrolment with QR code, confirmation, recovery codes; two-step login; disable; admin reset.
- [ ] OIDC login with the account resolution order from section 7; link and unlink in settings; `APP_PASSWORD_LOGIN_ENABLED`, including first-run setup through OIDC when password login is off.
- [ ] API tokens: create with scope and expiry, show once, list, revoke; Bearer authentication; scope enforcement and the blocked endpoint groups; the REST API (section 8).
- [ ] Full settings and admin screens, including the user list with invite, reset link, deactivate, delete, the admin rights toggle and TOTP reset, and the instance status.

Done when: pytest covers TOTP, recovery codes, token auth and token scope limits; OIDC is tested against a mock provider in pytest and manually against one real provider (Authentik or Keycloak in Docker), with the steps recorded in the report, and an unknown user is refused unless auto-provisioning is on. A read token can list notes with `curl` and is refused when it tries to create a note or touch the token endpoints.

## Phase 11: Release

- [ ] Startup configuration validation with clear messages.
- [ ] Complete the Playwright list in section 12 and run it in CI against the built image.
- [ ] Release workflow publishing a multi-architecture image (`linux/amd64` and `linux/arm64`) to GHCR on a version tag.
- [ ] `README.md` as described in section 11, with screenshots; `CONTRIBUTING.md`, `CHANGELOG.md`.
- [ ] Accessibility pass (section 9, Accessibility) and a review of the security headers with the final bundle.
- [ ] Design pass against section 9 "Visual design": no rounded corners, no raw colour values outside the tokens and the note palette, no stray shadows, mono used for timestamps and numbers.
- [ ] A full run-through on a clean volume using only the README.

Done when: a person following the README on a fresh machine has a working instance behind HTTPS, and the tagged image is on GHCR for both architectures (confirm with `docker buildx imagetools inspect`).
