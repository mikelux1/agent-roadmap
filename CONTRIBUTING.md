# Contributing

Thanks for looking. Two things to know first:

1. **The core is meant to stay one HTML file and one Python script** that a person can read top to bottom. That is the feature. Anything that needs a build step, a framework or a package manager belongs in a fork or a community version, not in the core.
2. **Download-and-edit is a first-class way to contribute.** The MIT license lets you copy, change and redistribute without asking. If you make something you like, tell us about it (see below) rather than feeling you have to get it merged.

## Bug reports and small fixes

Open an issue with what you did, what you expected and what happened. For fixes, a PR against `main` is great. Keep the diff focused; the files are hand-formatted and dense on purpose.

Before opening a PR, open `roadmap.html` in Chrome and check the console is clean, then run a quick smoke test of the script:

```bash
python3 roadmap.py --file /tmp/r.json init --demo
python3 roadmap.py --file /tmp/r.json add --section v1-2 --title "smoke" --pts 1
python3 roadmap.py --file /tmp/r.json changes --by agent --since 1h
```

## Community versions

Made a variation? Two options:

- **PR a folder into `community/`**: `community/<your-name>-<what-it-is>/` with your files and a short `README.md` (what changed, why, a screenshot if you have one). It ships alongside the original and gets listed in the top-level README.
- **Or open an issue** titled `Fork: <name>` linking your repo, and it gets listed too. Enable GitHub Pages on your fork so people can try it in one click.

Community folders are not reviewed for code quality, only for being on topic and safe to open.

## Ideas that would be welcome in the core

- Keyboard shortcuts
- A tiny test harness for the merge function (it's pure: `merge3(base, mine, theirs)`)
- Better mobile layout
- A Node or shell port of `roadmap.py` living next to it

## Ideas that are better as forks

- Multi-user, auth, hosted backends
- Gantt / timeline views
- Integrations with issue trackers
