# Changelog

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
