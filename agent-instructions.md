# Agent instructions for the roadmap

Paste the block below into the file your agent reads at the start of a session (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.github/copilot-instructions.md`, …). Adjust the path to wherever you put the two files.

---

## Roadmap

The project roadmap lives in `planning/roadmap-data.json`. The human edits it in a browser page that watches the file; you edit it **only** through `planning/roadmap.py`. Never edit the JSON by hand: the script stamps your changes so the human can see what you did, and it guards against overwriting a save from the browser.

**At the start of a session**

```bash
python3 planning/roadmap.py status                    # who touched the file last, open session?
python3 planning/roadmap.py changes --by human --mark # what the human changed since you last looked
python3 planning/roadmap.py ls --todo                 # what's open, by release
```

**When you change the plan**

```bash
python3 planning/roadmap.py begin "one-line summary of this update"
python3 planning/roadmap.py set <id> --done --note "DONE — what shipped, where"
python3 planning/roadmap.py set <id> --note "BUILT — needs a device test" --detail "<p>HTML notes for the side panel</p>"
python3 planning/roadmap.py add --section <release-id> --title "…" --pts 2 --note "…"
python3 planning/roadmap.py set <id> --section backlog          # move an item
python3 planning/roadmap.py rm <id>                              # goes to Trash, recoverable
python3 planning/roadmap.py end
```

Use `sections` to see release ids, `show <id>` to read an item, `ls --grep text` to find one. Effort points are agile estimates (`--pts`), a short `--note` is shown next to the title, and `--detail` is HTML for the side panel. Start a note with `DONE`, `BUILT` or `READY` when the ball is in the human's court.

**Rules**

- Group related writes between `begin` and `end` so they show up as one update in the human's highlight view.
- Don't mark an item done unless the work is actually merged or shipped; use a `BUILT —` note instead.
- Don't rewrite the human's notes; add to the detail HTML below them.
- If the script says the file changed under it, run the command again; it never writes blind.
