# Changelog

Notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-25

The first release, a beta: expect changes before 1.0.

### Added

- Text notes with bold, italic, underline and two heading sizes; checklists with a collapsible section of checked items, reordering and pasting several lines at once; conversion between the two.
- Images on notes, resized and compressed on the device, stored once per user however many notes use them, with an option to download them only when opened.
- Labels, twelve note colours, pinning, archive, trash with automatic purging after a number of days set by an admin, and local search that ignores case and accents.
- Masonry grid with two columns on phones and list view, drag to reorder with mouse or touch, multi-select with bulk actions and Undo.
- Offline-first sync: every change is saved on the device first and synced field by field, live through Server-Sent Events; concurrent edits of the same text keep the losing version as a conflict copy.
- Installable web app with offline start, an update prompt and safe-area handling on phones.
- Accounts: first-run setup, invite links, optional open registration, password reset links, two-step verification with recovery codes, single sign-on through OIDC, sessions that can be revoked.
- Administration: users, admin rights with guards against locking out the last admin, deactivation, deletion, storage quotas per user and an instance default, shown to each user as a usage bar in the navigation drawer, and the instance limits: days in the trash, the largest image and how long a sign-in lasts.
- Personal API tokens with read or write scope, and a REST API for notes and labels.
- Light and dark theme, saved in the profile.
- A multi-architecture Docker image (`linux/amd64`, `linux/arm64`) that serves the app and the API, with checks of the configuration at startup.

[0.1.0]: https://github.com/K-cermak/K-Notes/releases/tag/v0.1.0
