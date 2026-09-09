# Changelog

## 1.1.0 — 2026-09-09

Bulk actions and item numbers, ported from the private roadmap this tool was extracted from.

### Added

- **Per-release item numbers.** Every row carries a `1..n` number inside its release, so you and the agent can both say "item 3". Hidden done items drop out of the numbering; a search never renumbers. The side panel names the number too.
- **Bulk selection.** Tick rows and the release header becomes a bar: **Mark as done** (or not done), **Move…** to another release or the backlog, **Delete** to Trash, **Cancel**. Selection is scoped to one release at a time, so a bulk action always has one unambiguous source.
- **Block drag.** Dragging any ticked row drags the whole ticked set, keeping its relative order.

### Changed

- The row checkbox now **selects** instead of completing. Done is shown as a green ✓ before the title, and set either from the bulk bar or from the Done checkbox in the **✎ Edit** dialog.
- The demo seed explains both new features.

### Fixed

- The schema 2 → 3 migration in `roadmap.html` deleted the agent's change log instead of renaming it (`claudeLog` → `agentLog`), so a file from the private predecessor lost its session history in the browser. `roadmap.py` always migrated it correctly.
- Dragging a selected block into another release left the bulk bar behind on the old release, where its buttons did nothing.

## 1.0.0 — 2026-09-08

First public release. Extracted from a private project roadmap (internal v3.1) and made generic.

- `roadmap.html`: single-file board with releases, backlog, notes, trash, effort points, dark mode
- Live two-way sync with a JSON file on disk (File System Access API) with a field-level three-way merge
- **✨ last update** highlight showing everything the agent changed in its most recent session, with session history
- Conflict banner when a human edit overrides an agent edit
- `roadmap.py`: agent-side CLI with atomic, mtime-guarded writes, sessions, change stamps and a `changes --by human` inbox
- `init` command, `--file` / `ROADMAP_FILE`, note commands, `#item-id` deep links
- Demo seed with dummy entries that explain the features
- Schema 3 (`agentLog`, `by: human|agent`); schema 2 files migrate automatically
