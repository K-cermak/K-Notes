# K-Notes specification

## 1. Product

K-Notes is a self-hosted notes app for people who like Google Keep and want to own their data. One person or a small group (family, friends) runs one instance. Each user has private notes; there is no sharing between users.

The app is a web app. On phones it is used as a PWA added to the home screen, with no app store involved. It must work fully offline: create, edit, reorder and delete notes without a connection, then synchronise when the connection returns.

### In scope

- Text notes with basic formatting (bold, italic, underline, headings H1 and H2).
- Checklist notes.
- Images attached to notes.
- Labels, note colors, pin, archive, trash, search.
- Grid (masonry) and list view, manual ordering by drag, multi-select with bulk actions.
- Light and dark theme.
- Multiple user accounts: first-run setup creates the admin; admins invite further users by link; optional open registration.
- Login by password, optional TOTP second factor, optional OIDC single sign-on.
- An optional captcha on sign-in and registration (section 7, added after 0.1.0).
- Personal API tokens and a small REST API for scripts.
- Offline-first sync across devices, near-instant when online.

### Out of scope

Do not build these, and do not add hooks for them:

- Reminders, collaborators, sharing notes between users, public links.
- Drawings, audio notes, nested checklist items, note backgrounds (images behind notes).
- Import and export (backup is copying the data directory).
- Sending e-mail of any kind (no SMTP). An e-mail address is only a login name and the key for matching OIDC accounts.
- PostgreSQL or any second database backend.
- Native mobile apps, browser extensions.
- End-to-end encryption.

### Look and feel

The layout and interactions should feel like Google Keep's web app, described in section 9. The visual style is the owner's own, shared with their other products and specified in section 9 "Visual design"; the app is not meant to look like Keep at a glance. Do not use Google's name, logo, the Keep icon or Google's typefaces. The app has its own name and icon. The icon is the mark from the owner's logo, kept in `frontend/public/icon.svg` as the favicon, the source of the PWA icons and the logo in the top bar and drawer; the app shows it next to the name rather than using the wordmark, so a rename needs no new artwork in the app, and as a picture it is exempt from the colour rules of section 9. The source artwork and the wordmark versions are kept outside the repository and published on a CDN for the README and the website. The name lives only in `branding.json` at the repository root (app name, short name, description, theme colour); the backend, the frontend and the web manifest all read it from there.

## 2. Architecture

```
Browser (Vue PWA)
  UI  <->  Dexie (IndexedDB): notes, items, labels, attachments, blobs, outbox
                |
           sync engine  -- push ops / pull changes / SSE wake-up / blob transfer
                |
FastAPI  (/api/v1/*, and the built SPA on every other path)
  auth, sync, blobs, admin, tokens, notes
  services/merge.py  (single write path)
                |
        SQLite (WAL)  +  blob files          both under /data
```

Decisions and their reasons:

- **Local database is the UI's source of truth.** Components read from Dexie through live queries and write through repository functions. The network is only touched by the sync engine. This is what makes offline work and keeps the UI instant.
- **The server is the durable source of truth.** A browser may evict local data (iOS does this under storage pressure). Local data must always be rebuildable from the server; the only thing at risk is the outbox, so it is flushed as early as possible and its size is shown to the user.
- **SQLite only.** One container, one volume, backup by copying a directory. The expected scale is tens of users.
- **One server process.** SSE fan-out is an in-process registry and SQLite has a single writer. Run uvicorn with exactly one worker. Document this in the README; do not add Redis or a broker.
- **Sync SQLAlchemy sessions with plain `def` endpoints.** FastAPI runs them in its thread pool. Only the SSE endpoint is `async def`. Sync endpoints wake SSE listeners with `loop.call_soon_threadsafe`.
- **SSE rather than WebSocket.** The server only needs to tell clients "something changed, pull". SSE works through ordinary reverse proxies and reconnects by itself.
- **Field-level merge with conflict copies rather than a CRDT.** Notes are personal, so real conflicts are rare. Section 5 defines the rules.
- **Cookie sessions rather than JWT in localStorage.** HttpOnly cookies are not readable by script and work with `EventSource`.

### SQLite settings

Set on every connection: `journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`. Alembic migrations run automatically at startup before the app accepts requests.

### API conventions

Base path `/api/v1`, JSON. Errors have one consistent shape with a machine-readable code and a message. A resource that belongs to another user returns 404, not 403, so its existence is not revealed.

The frontend never hand-writes API types. FastAPI publishes an OpenAPI schema; `openapi-typescript` turns it into types and `openapi-fetch` gives a typed client, used by the sync engine and by the account, settings and admin screens. CI fails if the generated file is out of date.

The main resources, as a guide to the shape rather than a complete list:

| Area | Endpoints |
| --- | --- |
| Public | `GET /config`, `GET /health` |
| Auth | `POST /auth/setup`, `/auth/login`, `/auth/login/totp`, `/auth/logout`, `/auth/register`, `/auth/invite/*`, `/auth/password-reset/*`, `GET /auth/oidc/login`, `GET /auth/oidc/callback`, `GET /auth/captcha/challenge` |
| Account | `GET` and `PATCH /me`, `/me/password`, `/me/totp/*`, `/me/sessions`, `/me/tokens`, `/me/oidc` |
| Sync | `POST /sync/push`, `GET /sync/pull`, `GET /sync/events` (section 5.3) |
| Blobs | `HEAD`, `PUT` and `GET /blobs/{hash}` (section 6) |
| Notes for tokens | `/notes`, `/labels` (section 8) |
| Admin | `/admin/users`, `/admin/invites`, `/admin/settings`, `/admin/captcha`, `/admin/status` |

## 3. Configuration

All settings are environment variables with the neutral prefix `APP_`, so a rename of the project does not break deployments.

| Variable | Default | Meaning |
|---|---|---|
| `APP_DATA_DIR` | `/data` | SQLite file, blobs, generated secret key |
| `APP_BASE_URL` | none | Public URL, for example `https://notes.example.com`. Required. Used for invite and reset links, the OIDC redirect, cookie security and the origin check |
| `APP_SECRET_KEY` | generated | If unset, generated on first start and saved in `APP_DATA_DIR` |
| `APP_PASSWORD_LOGIN_ENABLED` | `true` | Set `false` to allow only OIDC. Refused at startup unless OIDC is configured |
| `APP_OIDC_DISCOVERY_URL`, `APP_OIDC_CLIENT_ID`, `APP_OIDC_CLIENT_SECRET` | none | OIDC is enabled when all three are set |
| `APP_OIDC_PROVIDER_NAME` | `SSO` | Label on the login button |
| `APP_OIDC_AUTO_PROVISION` | `false` | Create accounts for unknown OIDC users |
| `APP_TRUSTED_PROXIES` | none | Proxy addresses whose `X-Forwarded-*` headers are honoured |
| `APP_LOG_LEVEL` | `info` | |

If `APP_SECRET_KEY` is unset, a random key is generated on first start and stored in `APP_DATA_DIR/secret.key`, so self-hosters do not have to invent one. TOTP secrets are encrypted with a key derived from it, and it signs OIDC state.

Three limits are not environment variables but instance settings an admin changes in the administration, stored in the `settings` table, with these defaults until changed (moved there from environment variables by the owner before 0.1.0):

| Setting | Default | Range | Meaning |
|---|---|---|---|
| Delete notes from the trash after | `7` days | 0 to 3650 | Days before trashed notes are purged. `0` disables automatic purging. Shortening it asks for confirmation, as older notes are purged within the hour |
| Maximum image size | `10` MB | 1 to 100 | Largest accepted image upload. The reverse proxy's body size limit must allow it |
| Sign people out after inactivity | `180` days | 1 to 3650 | Sliding session lifetime. Long because an offline app should not log people out. A change applies to new sessions and to existing ones the next time they slide forward |

The app must start and be usable with nothing set except `APP_BASE_URL`. Validate configuration at startup and fail with a message that names the variable and the problem.

`GET /api/v1/config` is public and returns what the client needs before login: app name, version, whether first-run setup is still needed, whether registration is open, whether password login and OIDC are enabled, the OIDC button label, trash retention days, the image size limit, and the captcha: its provider, site key and whether sign-in and registration ask for it, or `null` when it is off.

## 4. Data model

IDs are UUIDs generated by the client with `crypto.randomUUID()`, so entities can be created offline. Timestamps are integers in milliseconds since the Unix epoch, UTC.

### Synced entities

Every synced row has these bookkeeping columns in addition to its own fields:

- `user_id`: owner. Every query filters by it.
- `seq`: the user's change counter value when this row last changed.
- `field_meta`: JSON map from field name to `{seq, at, dev}`: the change counter, the edit time and the device ID of the last write to that field.
- `deleted`: tombstone flag. A tombstoned row keeps its ID and bookkeeping and has its content cleared. Tombstones are kept permanently.

**notes**

| Field | Type | Notes |
|---|---|---|
| `id` | uuid | |
| `type` | `text` or `checklist` | Mutable; the client converts between them |
| `title` | string | Plain text, at most 1000 characters |
| `content` | JSON | Rich text document, section 4.1. Empty for checklists. At most 100 000 characters serialised |
| `color` | string | Palette key such as `coral`, or `default` |
| `pinned` | bool | |
| `archived` | bool | |
| `trashed_at` | int or null | Set when moved to trash |
| `position` | string | Fractional index, section 4.2 |
| `conflict_of` | uuid or null | Set on conflict copies; the ID of the original note |
| `created_at`, `updated_at` | int | `updated_at` changes only on content edits (title, content, items, images), not on pin, color or position |

**checklist_items**: `id`, `note_id` (immutable), `text` (plain, at most 1000 characters), `checked`, `position`. At most 1000 items per note.

**labels**: `id`, `name` (at most 50 characters). Names are unique per user, compared case-insensitively. If a push creates a label whose name already exists under a different ID (two devices created it offline), the server keeps both and appends ` (2)`, ` (3)` and so on to the incoming one.

**note_labels**: membership rows keyed by (`note_id`, `label_id`). The op entity ID is `"{note_id}:{label_id}"`. Removing a label from a note tombstones the row; adding it again clears the tombstone.

**attachments**: `id`, `note_id` (immutable), `blob_hash` (immutable), `mime`, `width`, `height`, `size`, `position`.

### Non-synced server tables

- **users**: `id`, `email` (unique, stored lowercase), `display_name`, `password_hash` (nullable for OIDC-only users), `is_admin`, `is_active`, `totp_secret` (encrypted), `totp_enabled`, `totp_last_step`, `oidc_issuer` and `oidc_subject` (nullable, unique together), `locale`, `theme` (system, light, dark), `default_view` (grid or list), `time_format` (24h or 12h, default 24h), `seq` (the change counter), `created_at`.
- **sessions**: `id` (SHA-256 of the cookie token), `user_id`, `auth_method` (password or oidc), `created_at`, `last_used_at`, `expires_at`, `user_agent`, `ip`.
- **api_tokens**: `id`, `user_id`, `name`, `token_hash`, `token_prefix` (shown in the UI so the user can tell tokens apart), `scope` (`read` or `write`), `created_at`, `last_used_at`, `expires_at` (nullable), `revoked_at` (nullable).
- **invites**: `token_hash`, `email` (optional), `created_by`, `expires_at`, `used_at`. The same mechanism with a `purpose` column serves password reset links. An invite link is valid for 7 days and a reset link for 24 hours; each works once.
- **recovery_codes**: `user_id`, `code_hash`, `used_at`.
- **blobs**: (`user_id`, `hash`) primary key, `size`, `mime`, `created_at`.
- **applied_ops**: (`user_id`, `op_id`) primary key, `result`, `created_at`. Makes pushes idempotent. Rows older than 30 days are pruned.
- **settings**: key and value. Holds `registration_enabled`, `default_storage_limit_bytes`, the instance limits `trash_retention_days`, `max_image_mb` and `session_days`, and `captcha` (JSON with the provider, where it applies, the site key and the secret key); a missing key means the default.

### 4.1 Rich text

`content` is a Tiptap (ProseMirror) JSON document restricted to: `doc`, `paragraph`, `heading` with level 1 or 2, `text`, `hardBreak`, and the marks `bold`, `italic`, `underline`. Links are not stored as marks; URLs in text are detected and made clickable at render time.

The server validates the document against this schema with Pydantic and rejects anything else. The client renders content only through Tiptap or a small renderer that walks the JSON. Never store or render HTML strings from the server; this is what keeps the app free of stored XSS.

The server and the client each have a function that turns a document into plain text (used for search, card previews in the REST API and type conversion).

### 4.2 Ordering

Notes, checklist items and attachments are ordered by `position`, a fractional index string (use the `fractional-indexing` npm package; implement the same key generation in Python only if the server ever needs to create positions, which is limited to conflict copies and the REST API). Sort ascending by `position`, then by `id` to break ties. A new note gets a key before the current first note, so it appears at the top. Moving an entity writes one field on one row, which merges cleanly.

Pinned and unpinned notes are two separate lists that share the position space.

## 5. Sync protocol

This is the core of the project. Implement and test it exactly as written.

### 5.1 Change counter

Each user has a counter `users.seq`. Every write to a synced row increments it and stamps the row's `seq`, inside the same transaction. A client remembers the highest `seq` it has pulled (its cursor) and asks for everything after it.

### 5.2 Ops

A client change is an op:

```json
{
  "op_id": "uuid",
  "entity": "note | checklist_item | label | note_label | attachment",
  "id": "entity id",
  "kind": "upsert | purge",
  "fields": { "title": "Shopping" },
  "base_seq": 41,
  "edited_at": 1794268800000
}
```

- `upsert` creates the row if it does not exist and otherwise sets the given fields. A create carries all required fields and `base_seq: 0`.
- `purge` permanently deletes: the row becomes a tombstone. Purging a note also tombstones its items, memberships and attachments.
- `base_seq` is the row's `seq` as the client last saw it from the server when the edit was made. It tells the server what the client's edit was based on.
- `edited_at` is the client's clock when the user made the edit.
- Moving to trash, archiving, pinning, checking an item and removing a label are all `upsert` ops on a field (`trashed_at`, `archived`, `pinned`, `checked`, `deleted`).

### 5.3 Endpoints

`POST /api/v1/sync/push`

```json
{ "device_id": "uuid", "ops": [ ... ] }
```

At most 200 ops per request, applied in order in one transaction. Response: `{ "seq": 57, "results": [ { "op_id": "...", "status": "applied | gone | rejected", "error": "..." } ] }`.

- `applied`: done, including the case where the op lost a conflict (the client learns the outcome from the next pull).
- `gone`: the target is a tombstone; the op was dropped.
- `rejected`: validation failed. `error` is a machine-readable code such as `invalid_content`, `too_large`, `blob_missing`, `not_found`.
- An `op_id` already in `applied_ops` returns its stored result without being applied again.

`GET /api/v1/sync/pull?since=41`

Returns every row with `since < seq <= since + 1000`, grouped by entity, tombstones included:

```json
{
  "seq": 1041,
  "has_more": true,
  "changes": { "notes": [], "checklist_items": [], "labels": [], "note_labels": [], "attachments": [] }
}
```

`seq` in the response is the new cursor (`min(since + 1000, users.seq)`). Because the counter is dense per user, the window bounds the response size without sorting across tables. The client repeats while `has_more` is true. A first sync uses `since=0`.

`GET /api/v1/sync/events`

Server-Sent Events. Sends `event: change` with the user's current `seq` as data whenever that user's counter moves, and a comment line every 25 seconds as a heartbeat. Send the header `X-Accel-Buffering: no` so nginx does not buffer. On a `change` event with a `seq` above its cursor the client pulls.

### 5.4 Server merge rules

For an `upsert` on an existing, non-tombstoned row, each field in the op is handled on its own:

1. Read `meta = field_meta[field]`, defaulting to `{seq: 0, at: 0, dev: null}`.
2. The write is **concurrent** when all three hold: `meta.seq > op.base_seq`, `meta.dev != device_id`, and the stored value differs from the incoming value.
3. Not concurrent: apply the incoming value.
4. Concurrent: the later edit wins. Let `t = min(op.edited_at, server_now)`. The incoming value wins when `t >= meta.at`; otherwise the stored value stays.
5. When a concurrent write involves a **content field** (`notes.title`, `notes.content`, `checklist_items.text`), the losing value must not be lost: record it for a conflict copy (5.5). Other fields are settled silently.
6. Every applied field gets `field_meta[field] = {seq: new_seq, at: t, dev: device_id}`.

The `meta.dev != device_id` test matters: a device that types quickly sends a second op whose `base_seq` predates the server's acknowledgement of its first. Without the test the device would conflict with itself.

Clamping `edited_at` to the server's clock stops a device with a clock set in the future from winning forever.

Other rules:

- An op on a tombstone returns `gone`. This means an offline edit to a note that was meanwhile permanently deleted is dropped. This is accepted: the note was either deleted on purpose or sat in the trash for the whole retention period.
- An `upsert` for a child (item, attachment, membership) whose note does not exist or is a tombstone returns `gone`.
- Trashing on one device and editing on another both apply, because they touch different fields. The note stays in the trash with the edit.
- An attachment create whose blob the server does not have is `rejected` with `blob_missing`; the client uploads the blob and retries.
- Setting any content field, or changing items or attachments, updates the note's `updated_at`.

### 5.5 Conflict copies

Before applying a push batch, the server lazily snapshots each note it is about to touch (the note with its items, memberships and attachments as they were before the batch). After the batch, for each note that recorded at least one losing content value, it creates one conflict copy:

- Start from the pre-batch snapshot. This already contains every stored value that an incoming write overwrote.
- Overlay every incoming content value that lost.
- Give the note and its items and attachments new IDs. Attachments point at the same `blob_hash`, so no image data is copied.
- Set `conflict_of` to the original note's ID, `pinned` to false, and a `position` immediately after the original.
- Stamp all `field_meta` with the new `seq` and `dev: "server"`.

The result: the original note holds the winning values and the copy holds the state that would otherwise have been overwritten. One push batch produces at most one copy per note. The client shows a small "Conflicted copy" marker on such notes, with an action to open the original; the marker disappears when the user dismisses it (which clears `conflict_of`).

### 5.6 Client sync engine

Local Dexie tables: `notes`, `checklistItems`, `labels`, `noteLabels`, `attachments`, `blobs`, `outbox`, `meta` (cursor, device ID, user ID, device settings, a cached copy of the profile settings).

**Writing.** A repository function applies the change to the local row and appends an op to `outbox` in one transaction. If an unsent op for the same entity already exists, merge the new fields into it and keep its original `base_seq`, instead of appending. Text input is debounced (about 800 ms) before it reaches the repository, and flushed immediately when the editor closes or the page is hidden.

**Sync cycle.** One cycle at a time, never in parallel:

1. Upload blobs that are stored locally and not yet on the server.
2. Push outbox ops in order, in batches of up to 200 ops and about 1 MB of JSON, so that a batch stays within the default request size limit of common reverse proxies (a single larger op is sent on its own). Hold back attachment ops whose blob is not uploaded yet. Remove ops from the outbox when the server answers `applied`, `gone` or `rejected`; log rejections and show a toast for them. `blob_missing` is the exception: keep the op and retry after uploading.
3. Pull until `has_more` is false.
4. Download blobs referenced by live attachments that are not stored locally (unless the device setting "download images on demand" is on).

**Applying a pulled row.** Write the server row to the local table and store its `seq` as the row's server version. If the outbox holds unsent ops for that entity, keep the local values of the fields those ops touch; they will be pushed and settled by the server. A pulled tombstone removes the local row and drops pending ops for it.

**Triggers.** Run a cycle on app start, on the browser `online` event, when the page becomes visible, on an SSE `change` event, and a short moment after any local write. On network failure retry with exponential backoff capped at 60 seconds. The Background Sync API is not available in Safari, so syncing happens only while the app is open; do not depend on it.

**Status.** The top bar shows sync state: synced, syncing, offline, or error, and the number of unsent changes when it is not zero. Clicking it opens a panel with the state in words, the number of unsent changes and of changes the server refused, the time of the last successful sync (kept on the device), and a "Sync now" button, or a sign-in link when the session has ended.

**Auth edge cases.**

- A `401` during sync keeps all local data and the outbox, stops syncing and asks the user to sign in again. After signing in as the same user, sync resumes.
- Signing in as a different user than the one whose data is stored locally wipes the local database first. If the outbox is not empty, warn and ask for confirmation.
- Signing out wipes the local database, with the same warning.
- With local data on the device, the app opens straight into it without waiting for the server, using the cached configuration and profile. The session is checked in the background: a `401` is handled like one during sync, a fresh profile replaces the cached one. This also covers a weak signal, where requests neither fail nor finish for a long time. Only a device without local data waits for the server at start. (Before 0.2 the app waited for the server whenever the network did not fail outright.)

### 5.7 Trash purging

A background task runs hourly and purges notes whose `trashed_at` is older than the trash period set by an admin (section 3; never when it is `0`). Purging goes through the merge service like a client `purge` op, so other devices learn about it through a normal pull. "Delete forever" and "Empty trash" in the UI are `purge` ops.

After purging, delete blob files that no live attachment of that user references any more.

## 6. Images

- **Client processing.** Before storing, decode the image and, if its longer edge exceeds 2560 px, scale it down to 2560 px. Re-encode to JPEG at quality 0.85 when the image was resized or is larger than 1 MB; otherwise keep the original bytes. Accept JPEG, PNG, WebP and GIF. GIFs are never re-encoded (it would drop animation). This cuts mobile data use in both directions, which matters because every device stores every image.
- **Identity.** A blob is identified by the SHA-256 of its bytes, in hex. Blobs never change, so each device transfers each blob at most once.
- **Local storage.** Blobs are stored in the Dexie `blobs` table as `Blob` values keyed by hash, with a flag for whether the server has them. Images can be attached offline; the upload happens in the next sync cycle.
- **Server storage.** `PUT /api/v1/blobs/{hash}` with the raw bytes. The server checks the size limit, verifies the hash, verifies with Pillow that the bytes are an image of an accepted type, and writes to `APP_DATA_DIR/blobs/ab/cd/{hash}`. `HEAD` tells the client whether an upload is needed. `GET` returns the bytes with `Cache-Control: private, immutable, max-age=31536000`.
- **Access control.** A user can read a blob only if a `blobs` row links that user to the hash. Knowing a hash is not enough.
- **Display.** Create object URLs only for cards that are on screen (IntersectionObserver) and revoke them when cards leave, so a grid with many photos does not exhaust memory.
- **Download on demand.** A per-device setting. When on, the sync cycle skips step 4, cards show a placeholder with the image's aspect ratio, and tapping it downloads that note's images. There is no automatic Wi-Fi detection because iOS does not expose the connection type to web pages.
- **Storage persistence.** After the first successful sign-in, call `navigator.storage.persist()`. Show the space the app takes on the device, from `navigator.storage.estimate()`, in the device settings, worded so it is not mistaken for the account quota: it includes the cached app itself and the downloaded images.

## 7. Authentication and accounts

- **First run and accounts.** When the database has no users, the app shows a setup screen that creates the admin. When `APP_PASSWORD_LOGIN_ENABLED` is false, the setup screen offers the OIDC button in place of the password form, and the first user to sign in through it becomes the admin, regardless of `APP_OIDC_AUTO_PROVISION`. After that, accounts come from three places: an invite link created by an admin (shown for copying, since the app sends no e-mail), self-registration if an admin has switched it on, or OIDC auto-provisioning if configured. Admins do not create accounts by hand or set other users' passwords. A user is identified by their e-mail address and has a display name.
- **Passwords.** Hash with Argon2id (`argon2-cffi`). Minimum length 10, no composition rules. Changing the password revokes all other sessions. Throttle failed logins per account and per IP with an in-memory counter and growing delays. Login responses must not reveal whether an e-mail address has an account.
- **Sessions.** A random 256-bit token in an `HttpOnly`, `SameSite=Lax` cookie, marked `Secure` whenever `APP_BASE_URL` is https; the database stores only its hash. Lifetime slides forward on use, up to the sign-in length set by an admin (section 3). Users can see and revoke their sessions. A nightly cleanup deletes expired sessions and used or expired invites.
- **CSRF.** For requests authenticated by cookie, reject any state-changing method whose `Origin` (or `Sec-Fetch-Site`) shows it came from another site. Requests authenticated by a Bearer token skip this check.
- **TOTP.** Optional, and each user decides for themselves (`pyotp`). Enrolment shows a QR code and the secret, and completes only after the user enters a valid code. It then shows 10 recovery codes once; store only their hashes. Each recovery code works once. Login becomes two steps: the password yields a short-lived pending token (5 minutes) that can only be exchanged, together with a TOTP or recovery code, for a session. Accept the previous and next time step to tolerate clock drift, and store the last accepted step so a code cannot be replayed. Turning TOTP off requires the password and a current code. Encrypt the secret at rest with a key derived from the secret key. A login through OIDC does not ask for TOTP, because second factors are then the identity provider's job.
- **OIDC.** One generic provider configured by discovery URL, using the authorization code flow with PKCE (Authlib) and the scopes `openid email profile`. The login page shows a button labelled with `APP_OIDC_PROVIDER_NAME` when OIDC is enabled. Resolving who is logging in, in this order:
  1. A user already linked to this issuer and subject logs in.
  2. Otherwise, if the provider says the e-mail is verified and a local user has that e-mail, link the two and log in.
  3. Otherwise, if `APP_OIDC_AUTO_PROVISION` is true, create the user, even when registration is closed.
  4. Otherwise refuse with a message that the account has to be created by an administrator first.

  Never link on an unverified e-mail: that would let anyone who can set an arbitrary e-mail at the provider take over an account. A signed-in user can also link and unlink their OIDC identity in settings. Unlinking is refused if it would leave the account with no way to log in. `APP_PASSWORD_LOGIN_ENABLED=false` hides the password form for instances that want OIDC only, and is refused at startup unless OIDC is configured.
- **API tokens.** A user creates named tokens in settings, choosing a scope and an optional expiry. The token is shown once and has a short fixed prefix followed by random characters, so leaked tokens are recognisable. Store its SHA-256 hash and the first few characters for display. Clients send it as `Authorization: Bearer`. `read` allows GET requests on note data; `write` additionally allows creating, changing and deleting it. No token can reach account, security or admin endpoints: password, TOTP, sessions, tokens, OIDC linking, user management. Settings shows each token's scope, expiry and last use, and can revoke it.
- **Admin.** List users, invite by link, produce a password reset link, reset a user's TOTP, deactivate or reactivate, delete (removes all the user's data and blobs), grant or revoke admin rights, toggle registration, configure the captcha. The admin area also shows instance status: version and whether OIDC is configured. An admin cannot see other users' notes. There can be several admins. Two guards, enforced on the server and reflected in the UI by disabled controls:
  - The instance always keeps at least one active admin: the last one cannot be demoted, deactivated or deleted.
  - Admins cannot revoke their own admin rights or deactivate or delete their own account from the admin screen, so nobody locks themselves out by accident.
  
  Deactivating a user or revoking admin rights takes effect immediately: deactivating deletes the user's sessions and their API tokens stop working, and admin checks read the current flag on every request. A deactivated account cannot log in by password or through OIDC, and its API tokens are refused.
- **Deleting one's own account.** Any user can delete their account in the security settings (`DELETE /api/v1/me`, not reachable with an API token). It is confirmed with the password, or, for an account that signs in only through single sign-on, by typing its e-mail address. It removes all the user's data like an admin's delete, and the client wipes the local data and goes to the login page. The last active admin cannot delete their account. (Added by the owner in 0.2.)
- **Lost passwords.** The app sends no e-mail. The login page says to ask the administrator, who generates a single-use reset link and passes it on; the user sets the new password themselves. For a locked-out admin: `docker exec <container> python -m app.cli reset-password <email>`. The CLI can also disable TOTP for a user (`disable-totp`), promote a user to admin (`make-admin`) and turn off the captcha (`disable-captcha`).
- **Secrets.** Session tokens, API tokens, invite and reset tokens and recovery codes are stored only as hashes and compared in constant time. Never log secrets, tokens or passwords.

### Storage quotas

Added during development at the owner's request.

- **What counts.** The text of the user's notes (titles, rich text and checklist items) and the user's images, each stored image once even when several notes use it. Notes in the trash count until they are purged.
- **Limits.** An instance default set by an admin, which may be unlimited (the default), and a per-user setting: the instance default, unlimited, or a custom size. Admins are always unlimited.
- **Over the limit** the user cannot create new notes (including copies) or add images. Editing existing notes, even making them longer, restoring from the trash, and everything else stays allowed, and so do reading and deleting, which brings the user back under the limit.
- **Enforcement.** The app knows the usage and the limit from `GET /me/storage`, refreshed after every sync cycle, and disables the actions above while the user is over. The server does not refuse sync pushes or image uploads because of the quota: a device that was offline could not have known, and its changes must not be lost, so they may take the user over the limit. The REST API for tokens, which is always online, refuses to create notes over the limit (`storage_full`). A modified client could therefore exceed the quota; it protects against accidents on a trusted instance, not against a hostile user.
- **Shown** at the bottom of the navigation drawer and in the Storage section of settings, as "X of Y used" with a usage bar, or as "X used" without a bar when the user has no limit; and in the admin user list with each user's usage and limit. (The drawer and the settings section were added by the owner before 0.1.0.)

### Captcha

Added after 0.1.0 at the owner's request.

- **Providers.** Google reCAPTCHA v2 (the "I'm not a robot" checkbox), Cloudflare Turnstile, hCaptcha, or ALTCHA. The first three are hosted: the browser loads their widget, and the server checks the token at their verification endpoint. ALTCHA is a proof of work that the server issues (`GET /auth/captcha/challenge`, 404 unless ALTCHA is chosen) and checks itself, with keys derived from the secret key; it needs no keys and contacts no third party. Each solved ALTCHA challenge is accepted once, remembered in memory until it expires, which is enough for one process.
- **Where.** The admin chooses sign-in, registration or both. Registration covers open registration and invite links. Only the password step of sign-in asks; the TOTP step, first-run setup, password reset links and OIDC do not.
- **Failures.** A missing or rejected token is refused with 400 `captcha_failed` before the password is checked, and does not count as a failed login. A provider that cannot be reached refuses the request with 502 `captcha_unavailable` rather than letting it through. Tokens work once, so the form shows a fresh widget after every failed attempt.
- **Keys.** The site key and the secret key are kept in `settings`; the secret key is never sent back to a browser. New keys, or a new hosted provider, take effect only with a token solved against them, which the admin page collects with a test widget, so a mistyped key cannot lock everyone out. When the provider rejects the secret key itself, the admin sees `captcha_secret_invalid`. If the keys stop working later, `python -m app.cli disable-captcha` turns the captcha off.
- **The frame.** The widget runs in a same-origin frame, `/captcha.html?provider=…&sitekey=…`, which passes the token to the form with `postMessage` and reports its height, so challenge pop-ups are not cut off. Only this page's Content-Security-Policy admits the provider's origins, from a fixed list per provider chosen by the `provider` parameter, and it allows `frame-ancestors 'self'`. The app's own policy never changes: the service worker keeps `index.html` with the headers it was first fetched with, so a policy that followed the admin's setting would not reach installed apps. For the same reason the service worker does not cache `/captcha.html`.

### Security headers

Send a Content-Security-Policy that allows scripts and styles only from the app's own origin, images from `self`, `blob:` and `data:`, and connections only to `self`. Also send `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `frame-ancestors 'none'`. All fonts and icons are bundled; the app loads nothing from third-party origins. The one exception is the captcha frame, when an admin chooses a hosted captcha (see Captcha above).

## 8. REST API for tokens

A small convenience API for scripts, under `/api/v1/notes`. It is a thin layer that builds ops and passes them to the merge service with the token's ID as device ID. The GET endpoints need a token with the `read` scope, the others need `write`.

- `GET /notes` with filters `archived`, `trashed`, `label`, `q` and pagination.
- `GET /notes/{id}`.
- `POST /notes` with `title`, and either `text` (plain text, converted to a document) or `items` (list of strings), plus optional `color`, `pinned`, `labels` (names; created if missing).
- `PATCH /notes/{id}` for `title`, `text`, `color`, `pinned`, `archived`, `trashed`.
- `DELETE /notes/{id}` moves to trash.
- `GET /labels`.

FastAPI's generated OpenAPI page documents it.

## 9. User interface

Build with Vue components styled with Tailwind. Dialogs, popovers, menus, selects and other interactive primitives are built on Reka UI (unstyled, accessible); everything else is the app's own. Icons are Lucide. The typefaces are Geist and Geist Mono. The look is specified under "Visual design" below.

### Layout

- **Top bar**: menu button, app icon and name, a wide search field, sync status, grid/list toggle, a display options menu (theme, images on demand; its icon is not the settings gear, which belongs to the settings page in the account menu), account menu. On phones the search field takes the available width and the secondary buttons move into the account menu.
- **Navigation drawer**: Notes, one entry per label, Edit labels, Archive, Trash, and at the bottom the account's storage use, linking to the Storage section of settings (section 7, Storage quotas); it is hidden while the drawer is collapsed to the rail. On desktop it collapses to an icon rail and expands on hover or with the menu button; whether it was left expanded is remembered on the device. On phones it is an overlay opened with the menu button, closed at start.
- **Composer**: on desktop, a "Take a note…" bar centred above the grid, with buttons for a new checklist and a new note with image. Clicking it expands in place to title, body and toolbar. On phones, a floating action button at the bottom right opens a full-screen editor.
- **Grid**: masonry columns of fixed card width (about 240 px), as many as fit; where fewer than two fit, as on a phone, two narrower columns share the width, as long as each stays at least 140 px wide, and only below that one column takes the full width, up to 600 px. (Two columns on phones were asked for by the owner before 0.1.0; it was one before.) Cards are 16 px apart, 8 px on phones (narrower than 640 px), where the owner found 16 px wasteful. A "Pinned" section and an "Others" section, each with a small uppercase heading, shown only when pinned notes exist. List view is a single centred column about 600 px wide.
- **Empty states**: a large faint icon and one line of text, per view (notes, archive, trash, label, search).

### Note card

- Square corners, a 1 px hairline border, the note's color as background. Hover darkens the border; there is no shadow.
- Content order: images at the top edge to edge (a collage when there are several), title, body or checklist preview, label chips.
- Long content is cut off with a fade. Checklists show unchecked items and then "N checked items", which opens the checked items right on the card, as in Keep; whether a note shows them is remembered on the device, and is the same on its card and in the editor.
- On hover (desktop): a select checkbox at the top left, a pin button at the top right, and a bottom toolbar with color, add image, archive and a "more" menu (delete, add label, make a copy, show or hide checkboxes).
- On touch devices there is no hover: tap opens the note, long-press starts selection, and the same actions live in the editor's toolbar.

### Editor

- Desktop: the card grows into a centred dialog about 600 px wide over a dimmed backdrop. Phones: full screen, with a back arrow at the top left that closes it, besides Close in the bottom toolbar. On phones the browser and system bars (`theme-color`) take the note's colour while it is open, so the status bar does not cut a band of page colour above a coloured note.
- The open note has its own route (`/note/:id`), so the browser back button and the Android back gesture close it.
- Title field, then the Tiptap body or the checklist. A new note starts with the cursor in the body or the checklist, as in Keep; the title is a click or Shift+Tab away. A formatting control offers H1, H2, normal text, bold, italic, underline and clear formatting. Standard shortcuts work (Ctrl/Cmd+B, I, U).
- Bottom toolbar: formatting, color, image, archive, more menu, "Edited" timestamp, Close.
- There is no save button. Changes are written continuously. A note left empty (no title, content, items or images) is discarded when the editor closes.
- Notes in the trash open read-only.

### Checklists

- Each item: drag handle, checkbox, text, remove button. Enter adds an item below; Backspace on an empty item removes it and moves focus up; pasting several lines creates several items.
- "+ List item" row at the bottom of the unchecked items.
- Checked items move to a collapsible "N checked items" section, struck through. It starts collapsed and opens and closes together with the one on the note's card. (The owner asked for one shared state in 0.2; the editor always opened it before.)
- Reorder by dragging the handle. Use `vue-draggable-plus` (SortableJS) here.
- Converting text to checklist makes one item per non-empty line of the plain text. Converting back joins the items with line breaks. Formatting is lost in conversion; that is acceptable.

### Colors

Twelve choices, stored as keys. A note's color fills the whole card, not a tint with a bar: in a grid of notes, color is the main way to tell them apart. These hex values are a starting point modelled on Keep's palette; check each one next to the tokens in "Visual design", with `ink` text on it, in both themes, and adjust.

| Key | Light | Dark |
|---|---|---|
| `default` | `bg` token | `bg` token |
| `coral` | `#faafa8` | `#77172e` |
| `peach` | `#f39f76` | `#692b17` |
| `sand` | `#fff8b8` | `#7c4a03` |
| `mint` | `#e2f6d3` | `#264d3b` |
| `sage` | `#b4ddd3` | `#0c625d` |
| `fog` | `#d4e4ed` | `#256377` |
| `storm` | `#aeccdc` | `#284255` |
| `dusk` | `#d3bfdb` | `#472e5b` |
| `blossom` | `#f6e2dd` | `#6c394f` |
| `clay` | `#e9e3d4` | `#4b443a` |
| `chalk` | `#efeff1` | `#232427` |

Page background, borders and text come from the tokens in "Visual design".

### Visual design

The layout and behaviour follow Keep; the look does not. The owner wants the look of Vercel's design language, in the specific variant used across their other products. It was taken from the stylesheet of one of those products (a contact form) and is now built into the design tokens in `frontend/src/styles/tokens.css` and the shared elements in `ui.css`. New UI builds on those and should look like it belongs to the same family.

What defines the style:

- **Monochrome first.** Near-black ink on white, near-white on near-black. Greys do the structural work. The accent blue is rare: the primary action, links, the selected state. Colour otherwise belongs to the user's notes, which is what makes them easy to tell apart.
- **Square corners.** Border radius is zero on everything: buttons, inputs, note cards, dialogs, chips, checkboxes, colour swatches, the floating button. The only round thing is a loading spinner. This is the trait that separates the owner's variant from stock Vercel, so do not soften it.
- **Hairlines, not shadows.** Surfaces are separated by 1 px borders in the line colour. Cards and panels have no shadow. Popovers, menus, snackbars and a card being dragged float above a busy grid, so they get the border plus one soft shadow token; the editor dialog also dims the page behind it.
- **Geist, and Geist Mono for codes.** Geist for everything, with tabular figures for numbers that should align or read as data: the "Edited" timestamp, counts (selected notes, checked items, unsent changes), storage use. Geist Mono only for codes read character by character: API tokens, the TOTP secret, recovery codes. (Changed by the owner before 0.1.0; numbers were mono before.) Self-host both through their npm font packages. Do not load them from Google Fonts: the app must work offline, under a strict CSP, and without telling a third party who uses it.
- **Small, dense type.** 14 px base, 13 px medium-weight labels in the muted colour, 12 px meta in the muted colour with tabular figures. Headings and note titles are weight 600 with slightly negative letter spacing. Nothing heavier than 600.
- **Thin square icons.** Lucide, drawn at stroke width 1.6 with square line caps and mitred joins set globally, so they match the reference's icons.
- **Quiet state changes.** Hover darkens a border or tints the background with a few percent of ink (`color-mix`), and only applies under `(hover: hover) and (pointer: fine)` so that touch devices do not get stuck hover states. Focus shows an ink border with a 3 px translucent ring on inputs, and a 2 px ink outline on buttons and links. Colour transitions take 150 ms. Movement is small (a few pixels) and uses the reference's ease-out curve. Under `prefers-reduced-motion`, movement becomes a fade or nothing.

Tokens. Define these as CSS custom properties using `light-dark()`, with `color-scheme` on the root switched by a `data-theme` attribute, and expose them to Tailwind as theme colours. Components use the tokens and the note palette only, never raw colour values.

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `bg` | `#ffffff` | `#0a0a0a` | Page and surfaces |
| `ink` | `#171717` | `#ededed` | Text, focused borders |
| `muted` | `#666666` | `#a1a1a1` | Secondary text, labels, meta |
| `faint` | `#8f8f8f` | `#8f8f8f` | Placeholders, disabled controls, decorative icons; never text that carries information, as it is below 4.5:1 on white |
| `line` | `#eaeaea` | `#2e2e2e` | Borders, grid lines |
| `line-hover` | `#c9c9c9` | `#454545` | Hovered borders |
| `accent` | `#1f6fd6` | `#1f6fd6` | Primary action, links, selection |
| `accent-hover` | `#1a5fc8` | `#1a5fc8` | |
| `danger` | `#d1242f` | `#ff6369` | Errors, destructive actions |
| `warning` | `#b45309` | `#f5a524` | |
| `scrim` | black at 30 % | black at 60 % | The dimmed backdrop behind dialogs and the phone drawer; black in both themes, so it darkens a dark page instead of washing it out |
| `success` | `#18803a` | `#3fb950` | Darker than the reference's `#1a8c3e`, which is 4.3:1 on white, so that it can be used for text |

Applying it to notes, which the reference does not cover:

- **Cards.** A hairline border in `line`, filled with the note's colour; a `default` note is filled with `bg`. Hover darkens the border to `line-hover`, a selected card has an `ink` border. Title and text are `ink` on every note colour.
- **Secondary text on a coloured note.** Inside a card or the editor of a coloured note, `muted` is replaced by 85 % `ink` mixed into the note colour: plain `muted` falls to 2.6:1 on some note colours, the mix keeps at least 4.5:1 on all twelve in both themes.
- **Label chips.** A hairline box with the label name. On a coloured card the border is a few percent of ink mixed into the note colour, so it stays visible.
- **Controls.** Inputs are 40 px high. The composer is a hairline box on `bg`. Primary buttons are solid accent with white text; secondary buttons are a hairline border on `bg`; destructive actions use `danger` as text or border and are never solid by default. Checkboxes are squares, filled with ink when checked.
- **Banners and snackbars** follow the reference's notice: a border and a faint tint of one tone colour, with a thin icon.
- **Phone.** The editor is full screen; menus and sheets rise from the bottom with square corners and a hairline top border. Tap targets are at least 44 px even where the visual is smaller.

Themes follow the system by default, with light and dark as explicit choices in settings. Theme, language, default view and time format are saved in the user's profile, so they follow the user across devices, and cached locally so the app opens in the right theme offline. A change made offline applies at once and is sent when the connection returns.

Times (the "Edited" timestamp, sync status, sessions, tokens) use a 24-hour clock unless the user picks 12-hour in settings, whatever the language. (Added by the owner in 0.2.)

### Ordering and selection

- **Drag to reorder notes.** Implement the masonry layout as a composable that measures card heights (ResizeObserver) and positions cards absolutely with transforms. Build note dragging on top of it with pointer events: on desktop drag starts after a few pixels of movement, on touch after a long-press. Other cards animate out of the way. Dropping writes a new `position`. Dragging between the Pinned and Others sections is not supported. Evaluate an existing library first, but generic sortable libraries assume uniform grids or lists and tend to fight masonry; do not spend long forcing one to fit.
- **Multi-select.** Selecting any note replaces the top bar with a selection bar: count, pin, color, labels, archive, delete, clear. On desktop, Shift+click selects a range, and dragging the mouse from empty space draws a rectangle that selects the notes it touches (with Shift, Ctrl or Cmd it adds to the selection); on touch, long-press selects. A click or tap on empty space clears the selection.

### Other behaviour

- **Search** runs locally over title, body text, checklist items and label names. It ignores case and diacritics (normalise with NFD and strip combining marks). Keep a derived `searchText` field on local notes. Results show in the grid, split into active and archived. Trashed notes are excluded.
- **Labels**: "Edit labels" dialog to create, rename and delete. A label picker with a filter field and "Create '<text>'" on notes and in bulk actions. Deleting a label removes it from notes and keeps the notes.
- **Undo**: archiving, trashing and deleting a label show a snackbar at the bottom left with an Undo action for a few seconds.
- **Make a copy** duplicates a note with its items, labels and image references.
- **Keyboard**: `c` new note, `l` new checklist, `/` focus search, `Esc` close editor or clear selection, `Ctrl/Cmd+Enter` close editor.
- **Trash view**: a notice saying notes are deleted after N days (from `/config`; hidden when purging is off) and an "Empty trash" button. Cards offer restore and delete forever.
- **Settings**: theme, language, default view, time format, download images on demand and the space the app takes on this device, account storage use, display name, password change, TOTP, OIDC link and unlink, sessions, API tokens. Admins also see user management with storage quotas, the registration toggle, the captcha, the default storage quota, the instance limits from section 3 and instance status.
- **Internationalisation**: all UI text lives in `frontend/src/locales/en.json` and is used through vue-i18n. Adding a language must need nothing more than a new JSON file and one entry in a list of available locales. English is the only language shipped. The chosen language is saved in the profile as `locale`.
- **Routes**: the account pages are `/setup`, `/login`, `/invite/:token`, `/reset/:token`, `/settings/*` and `/admin/*`.
- **Zoom**: the app does not zoom like a web page: no pinch or double-tap zoom, and no zoom when a field gets focus on iOS (the viewport's `maximum-scale=1`, plus cancelled pinch gestures on iOS, which ignores it). The image viewer is the exception, so a photo can be looked at closely. (Asked for by the owner in 0.2.)
- **Accessibility**: every icon button has an accessible name, dialogs trap focus and restore it on close, everything is reachable by keyboard, and color is never the only signal. Known limitation, accepted by the owner: reordering notes and checklist items works only by dragging with a pointer or touch, as in Keep; there is no keyboard equivalent. Another, decided by the owner in 0.2: the page cannot be zoomed outside the image viewer (see Zoom above), so the axe rule `meta-viewport` is switched off in the accessibility test.

## 10. PWA

- `vite-plugin-pwa` in `generateSW` mode. Precache the app shell and all bundled assets. Navigation requests fall back to `index.html`. Never cache `/api/` or the captcha frame `/captcha.html`.
- Web manifest with its name, short name and theme colour taken from `branding.json`, the app's icons, `display: standalone`, theme colors for both themes, and maskable icons. Add `apple-touch-icon` and the iOS meta tags.
- When a new version is available, show a snackbar "Update available" with a Reload action. Do not reload by itself; the user may be typing.
- On iOS Safari outside standalone mode, show a dismissible hint explaining Share → Add to Home Screen. This matters beyond convenience: Safari may delete a site's data after seven days without use, and home screen apps are exempt.
- Service workers require HTTPS (or `localhost`). The README must say that the app has to be served over HTTPS behind a reverse proxy, with a sample configuration that disables buffering for the SSE path and raises the request body limit (`client_max_body_size` in nginx) above the image size limit and the largest single note.
- Respect safe-area insets on phones, and make sure the on-screen keyboard does not cover the editor toolbar.

## 11. Docker and release

- Multi-stage `Dockerfile`: a Node stage builds the frontend, a slim Python stage installs the backend with `uv` and copies the built files. FastAPI serves them, with `index.html` for unknown non-API paths.
- Runs as a non-root user. One volume at `/data`. Port 8000. A `HEALTHCHECK` on `GET /api/v1/health`.
- `docker-compose.yml` in the repository is a working example with the image, the volume and the common environment variables, with OIDC shown commented out.
- A `justfile` holds the developer commands listed in `CLAUDE.md`; CI calls the same recipes.
- GitHub Actions:
  - On every push and pull request: backend lint, types and pytest; frontend lint, typecheck and Vitest; a check that the generated API types are current; Playwright against the built image.
  - On a `v*` tag: build a multi-architecture image for `linux/amd64` and `linux/arm64` (Docker Buildx; Raspberry Pi and ARM NAS devices are common among self-hosters) and push to GHCR with the version and `latest` tags. Avoid dependencies that lack prebuilt arm64 wheels, so the arm64 build does not compile native code under emulation.
- License: MIT.
- `README.md`: what it is, screenshots, quick start with Docker Compose, configuration table, reverse proxy and HTTPS notes, backup and restore (stop the container, copy `/data`), admin CLI, how to add a translation, development setup.
- `CONTRIBUTING.md`. Release notes are written by hand on each GitHub release; there is no changelog file.

## 12. Testing

- **pytest**: every merge rule in 5.4 and 5.5 as separate cases (clean apply, concurrent content edit with each side winning, same-device follow-up op, non-content field, tombstones, idempotent replay, one copy per note per batch, label name collision); pull windowing; trash purge and blob cleanup; auth flows including first-run setup, invites, reset links, the admin guards, TOTP, OIDC against a fake provider, the captcha against fake verification endpoints and with real ALTCHA solutions, and token scopes; user isolation (one user can never read or write another's rows or blobs, and gets 404 for them).
- **Vitest** with `fake-indexeddb`: outbox coalescing, applying pulled rows under pending ops, the sync cycle order, retry and `401` handling, image processing decisions, search normalisation.
- **Playwright**: first-run setup and first note; two browser contexts where a change in one appears in the other; an offline edit that syncs after reconnecting (`context.setOffline`); a concurrent offline edit of the same note that produces a conflict copy; attaching an image offline; reload while offline; signing in with ALTCHA turned on.
