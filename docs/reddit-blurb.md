**Agent Roadmap** is a release roadmap you and your coding agent edit together. One HTML file, one Python script, one JSON file in your repo. No install, no server, no accounts.

**The problem it fixes:** the plan for an agent-driven project ends up in a `TODO.md` the agent keeps rewriting, so you can't see what actually moved. Or it lives in a chat transcript that's gone when the context window fills.

**How it works**

- You open `roadmap.html` in Chrome and get a board: releases with a status, a backlog, effort points, notes, trash.
- The page links to `roadmap-data.json` on disk and autosaves to it.
- Your agent edits the same file through `roadmap.py` (Claude Code, Codex, Cursor, Copilot, Aider, anything that can run a script). Paste one snippet into your `CLAUDE.md` or `AGENTS.md` and it knows the commands.
- Every change the agent makes is stamped. Flip the **✨ last update** toggle and the board rings exactly what it added, edited, moved or deleted in its most recent session. You can step back through earlier sessions too.
- If you both touch the same field, your edit wins and the agent's version shows up in a banner. Nothing is lost silently.
- A fresh agent session runs `roadmap.py changes --by human` and knows what you changed while it was away.

**Why try it over the alternatives**

- It's a release roadmap, not a task tracker. Releases are the unit, items live inside them, and the backlog is where things wait.
- Zero runtime. Backlog.md, Beads, vibe-kanban and Task Master are all good, and all need Node, Go, Rust, Docker or an MCP server. This is two files you can read top to bottom.
- Download and edit is the intended way to use it. MIT, so change whatever you want.

**Try it in 30 seconds:** the live demo at https://mikelux1.github.io/agent-roadmap/ loads a dummy project with entries that explain each feature. Turn on ✨ last update to see a demo agent session highlighted.

**Get it:** https://github.com/mikelux1/agent-roadmap (grab `roadmap.html` and `roadmap.py` from the latest release, run `python3 roadmap.py init --project "My app" --agent Claude`, open the HTML, link the file).

Honest limits: live file sync is Chrome/Chromium only (other browsers fall back to browser storage plus export/import), it's single human plus single agent, and history is git plus the last 12 agent sessions. It's quick and dirty on purpose.
