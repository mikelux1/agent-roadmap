#!/usr/bin/env python3
"""
roadmap.py — the agent's side of the roadmap.

Reads and writes roadmap-data.json, the same file roadmap.html keeps open in
Chrome. Every write is atomic (os.replace) and guarded by an mtime check, so it
can never land on top of a browser save it didn't see.

Every node this tool touches gets stamped:  mt (ISO timestamp), by="agent",
sess (the id of the update session). The HTML reads those stamps to draw the
"✨ last update" highlight. The browser stamps its own edits by="human", which
is how `changes --by human` works below.

  init [--project NAME] [--agent NAME] [--demo]   create a fresh roadmap-data.json
  status                     what's in the file, who touched it last
  ls [--section S] [--grep T] [--todo|--done] [--by human|agent]
  show <id>
  sections
  changes [--by human] [--since last|ISO|12h] [--mark]
  seen                       mark everything up to now as read
  begin [note] / end         group the next writes into one update session
  set <id> [--title T] [--note N] [--detail H] [--done|--undone]
           [--pts N|--no-pts] [--section S]
  add --section S --title T [--note N] [--detail H] [--pts N] [--after ID]
  rm <id>
  rel-set <id> [--title T] [--status planned|inprogress|submitted|released] [--sub S]
  rel-add --title T [--status S] [--sub S]
  note-add --title T --html H
  note-set <id> [--title T] [--html H]

The data file is roadmap-data.json next to this script, or wherever
--file / $ROADMAP_FILE points.

https://github.com/mikelux1/agent-roadmap · MIT
"""
import argparse, json, os, re, sys, tempfile, time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("ROADMAP_FILE") or os.path.join(HERE, "roadmap-data.json")
SIDE = None                    # set once DATA is final: .roadmap-agent.json next to the data file
SESSION_IDLE_MIN = 90          # a session auto-closes after this much quiet
LOG_CAP = 12                   # keep this many update sessions in the file
SCHEMA = 3

now_iso = lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def set_paths(path):
    global DATA, SIDE
    DATA = os.path.abspath(path)
    SIDE = os.path.join(os.path.dirname(DATA), ".roadmap-agent.json")

# ── sidecar (agent-local, not shared with the browser) ──
def side_load():
    try:
        with open(SIDE) as f: return json.load(f)
    except Exception:
        return {"session": None, "session_at": None, "watermark": None}

def side_save(s):
    with open(SIDE, "w") as f: json.dump(s, f, indent=2)

# ── data file ──
def empty_state(project=None, agent=None):
    s = {"schema": SCHEMA, "releases": [], "backlog": {"open": True, "items": []},
         "notes": [], "trash": [], "agentLog": [], "modified": now_iso()}
    if project: s["project"] = project
    if agent: s["agent"] = agent
    return s

def migrate(s):
    """schema 2 (the private predecessor) → 3: neutral field names."""
    if s.get("schema") == 2:
        if "claudeLog" in s:
            s.setdefault("agentLog", s["claudeLog"]); del s["claudeLog"]
        by = {"mike": "human", "claude": "agent"}
        for nd in index(s).values():
            if nd["node"].get("by") in by: nd["node"]["by"] = by[nd["node"]["by"]]
        s["schema"] = SCHEMA
    s.setdefault("notes", []); s.setdefault("trash", []); s.setdefault("agentLog", [])
    return s

def load():
    if not os.path.exists(DATA):
        sys.exit("no roadmap file at %s — run:  roadmap.py init   (or open roadmap.html and press Save)" % DATA)
    with open(DATA) as f: s = json.load(f)
    if s.get("schema") not in (2, SCHEMA) or "releases" not in s or "backlog" not in s:
        sys.exit("%s is not a roadmap JSON (schema %r)" % (DATA, s.get("schema")))
    return migrate(s), os.path.getmtime(DATA)

def atomic_write(state, expect_mtime):
    """Write only if nobody else has touched the file since we read it."""
    if expect_mtime is not None and os.path.getmtime(DATA) != expect_mtime:
        return False
    state["modified"] = now_iso()
    d = os.path.dirname(DATA)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".roadmap-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA)
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise
    return True

def transaction(fn, tries=4):
    """fn(state) -> (changes, result). Retries if the browser saved mid-flight."""
    for attempt in range(tries):
        state, mt = load()
        changes, result = fn(state)
        if changes:
            record_session(state, changes)
        if atomic_write(state, mt):
            return result
        time.sleep(0.25 * (attempt + 1))
    sys.exit("roadmap-data.json kept changing under us (browser is saving fast) — nothing written, try again.")

# ── sessions ──
def record_session(state, changes):
    side = side_load()
    log = state.setdefault("agentLog", [])
    sid, sat = side.get("session"), side.get("session_at")
    stale = True
    if sid and sat:
        try:
            stale = datetime.now(timezone.utc) - datetime.fromisoformat(sat.replace("Z", "+00:00")) > timedelta(minutes=SESSION_IDLE_MIN)
        except Exception:
            stale = True
    entry = next((e for e in log if e.get("id") == sid), None) if sid and not stale else None
    if entry is None:
        # keep the id if a session is open but its entry vanished with a discarded retry
        note = side.get("pending_note") or ""
        if not (sid and not stale):
            sid = "c-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        entry = {"id": sid, "at": now_iso(), "note": note, "changes": []}
        log.append(entry)
        del log[:-LOG_CAP]
        side["pending_note"] = None
    entry["at"] = now_iso()
    by_id = {c["id"]: c for c in entry["changes"]}
    for c in changes:
        c["at"] = entry["at"]
        prev = by_id.get(c["id"])
        if prev:
            # same node touched twice in one session — keep the earliest kind, union the fields
            if prev["kind"] == "add" and c["kind"] == "delete":
                entry["changes"].remove(prev); del by_id[c["id"]]   # net zero: never existed for the human
                continue
            prev["fields"] = sorted(set(prev.get("fields", [])) | set(c.get("fields", [])))
            prev["title"] = c["title"]
            if prev["kind"] == "add" and c["kind"] in ("edit", "move"): pass
            elif c["kind"] == "delete": prev["kind"] = "delete"; prev["section"] = c.get("section", prev.get("section"))
            elif prev["kind"] != "add": prev["kind"] = c["kind"]
        else:
            entry["changes"].append(c); by_id[c["id"]] = c
    side["session"] = entry["id"]; side["session_at"] = entry["at"]
    side_save(side)
    for c in changes:
        c.setdefault("sess", entry["id"])
    # stamp the live nodes with the session id
    idx = index(state)
    for c in changes:
        nd = idx.get(c["id"])
        if nd and c["kind"] != "delete":
            nd["node"]["sess"] = entry["id"]

# ── navigation ──
def sections(state):
    out = [(r["id"], r.get("title", r["id"]), r) for r in state.get("releases", [])]
    out.append(("backlog", "Backlog", state["backlog"]))
    return out

def sec_by_id(state, sid):
    if sid == "backlog": return state["backlog"]
    return next((r for r in state.get("releases", []) if r["id"] == sid), None)

def index(state):
    m = {}
    for r in state.get("releases", []):
        m[r["id"]] = {"kind": "release", "node": r, "section": None}
        for it in r.get("items", []):
            m[it["id"]] = {"kind": "item", "node": it, "section": r["id"]}
    for it in state["backlog"].get("items", []):
        m[it["id"]] = {"kind": "item", "node": it, "section": "backlog"}
    for nt in state.get("notes", []):
        m[nt["id"]] = {"kind": "note", "node": nt, "section": None}
    return m

def need(state, iid):
    nd = index(state).get(iid)
    if not nd: sys.exit("no node with id %r — try:  roadmap.py ls --grep <text>" % iid)
    return nd

def stamp(node):
    node["mt"] = now_iso(); node["by"] = "agent"

def num(v):
    """3.0 → 3, 2.5 stays 2.5"""
    return int(v) if v is not None and float(v).is_integer() else v

def newid(pfx="c"):
    return pfx + format(int(time.time() * 1000), "x") + format(os.getpid() % 4096, "03x")

def plain(html, n=90):
    t = re.sub(r"<[^>]+>", "", html or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] + ("…" if len(t) > n else "")

# ═══════════ commands ═══════════
def cmd_init(a):
    if os.path.exists(DATA) and not a.force:
        sys.exit("%s already exists — pass --force to overwrite it." % DATA)
    if a.demo:
        demo = os.path.join(HERE, "example", "roadmap-data.json")
        if not os.path.exists(demo):
            sys.exit("no example/roadmap-data.json next to this script — download it from the repo, or run init without --demo.")
        with open(demo) as f: state = migrate(json.load(f))
        if a.project: state["project"] = a.project
        if a.agent: state["agent"] = a.agent
    else:
        state = empty_state(a.project, a.agent)
    atomic_write(state, None)
    print("wrote %s" % DATA)
    print("now open roadmap.html in Chrome and use the banner to link this file.")

def cmd_status(a):
    state, mt = load()
    idx = index(state)
    items = [v for v in idx.values() if v["kind"] == "item"]
    done = sum(1 for v in items if v["node"].get("done"))
    print("%-19s %d releases · %d items (%d done) · modified %s"
          % (os.path.basename(DATA), len(state.get("releases", [])), len(items), done, state.get("modified", "?")))
    if state.get("project"): print("project             %s" % state["project"])
    print("file mtime          %s" % datetime.fromtimestamp(mt).strftime("%Y-%m-%d %H:%M:%S"))
    log = state.get("agentLog", [])
    if log:
        e = log[-1]
        print("last agent update   %s · %d change(s)%s" % (e["at"], len(e.get("changes", [])), (" — " + e["note"]) if e.get("note") else ""))
    else:
        print("last agent update   (none yet)")
    side = side_load()
    wm = side.get("watermark")
    human = [v for v in idx.values() if v["node"].get("by") == "human" and (not wm or v["node"].get("mt", "") > wm)]
    print("human changes       %d since %s" % (len(human), wm or "the beginning of stamping"))
    if side.get("session"):
        print("open session        %s (auto-closes after %d min idle)" % (side["session"], SESSION_IDLE_MIN))

def cmd_sections(a):
    state, _ = load()
    for sid, title, sec in sections(state):
        its = sec.get("items", [])
        d = sum(1 for i in its if i.get("done"))
        print("%-14s %-3s %2d/%-2d  %s" % (sid, (sec.get("status") or "")[:3], d, len(its), title))

def cmd_ls(a):
    state, _ = load()
    for sid, title, sec in sections(state):
        if a.section and a.section != sid: continue
        rows = []
        for it in sec.get("items", []):
            if a.grep and a.grep.lower() not in (it.get("title", "") + " " + (it.get("note") or "")).lower(): continue
            if a.todo and it.get("done"): continue
            if a.done and not it.get("done"): continue
            if a.by and it.get("by") != a.by: continue
            rows.append(it)
        if not rows: continue
        print("\n── %s  (%s)" % (title, sid))
        for it in rows:
            who = it.get("by", "")
            tag = {"human": " [human]", "agent": " [agent]"}.get(who, "")
            print("  %s %-22s %-52s%s%s" % ("x" if it.get("done") else " ", it["id"], it.get("title", "")[:52],
                                            (" · " + str(it["pts"]) + "p") if it.get("pts") else "", tag))
    if a.section is None:
        notes = state.get("notes", [])
        if notes:
            print("\n── Notes")
            for n in notes:
                print("    %-22s %s" % (n["id"], n.get("title", "")[:60]))

def cmd_show(a):
    state, _ = load()
    nd = need(state, a.id); n = nd["node"]
    print("id       %s  (%s in %s)" % (n.get("id"), nd["kind"], nd["section"] or "-"))
    for k in ("title", "note", "status", "sub", "done", "pts", "mt", "by", "sess"):
        if n.get(k) not in (None, ""): print("%-8s %s" % (k, n[k]))
    if n.get("detail"): print("detail   %s" % plain(n["detail"], 400))
    if n.get("html"): print("html     %s" % plain(n["html"], 400))

def parse_since(s, side):
    if not s or s == "last": return side.get("watermark")
    m = re.fullmatch(r"(\d+)([hd])", s)
    if m:
        d = timedelta(hours=int(m.group(1))) if m.group(2) == "h" else timedelta(days=int(m.group(1)))
        return (datetime.now(timezone.utc) - d).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return s

def cmd_changes(a):
    state, _ = load()
    side = side_load()
    since = parse_since(a.since, side)
    idx = index(state)
    rows = []
    for iid, nd in idx.items():
        n = nd["node"]
        if a.by and n.get("by") != a.by: continue
        if not n.get("mt"): continue
        if since and n["mt"] <= since: continue
        rows.append((n["mt"], iid, nd))
    rows.sort()
    who = a.by or "anyone"
    print("%d change(s) by %s since %s\n" % (len(rows), who, since or "(no watermark — showing all stamped nodes)"))
    for mt, iid, nd in rows:
        n = nd["node"]
        print("  %s  %-22s %-8s %s%s" % (mt[:19].replace("T", " "), iid, "[" + (n.get("by") or "?") + "]",
                                         n.get("title", "")[:56], "  ✓done" if n.get("done") else ""))
        if n.get("note"): print("%s└ %s" % (" " * 26, n["note"][:80]))
    if a.mark:
        side["watermark"] = now_iso(); side_save(side)
        print("\nwatermark moved to now.")

def cmd_seen(a):
    side = side_load(); side["watermark"] = now_iso(); side_save(side)
    print("watermark → %s" % side["watermark"])

def cmd_begin(a):
    side = side_load()
    side["session"] = None; side["session_at"] = None
    side["pending_note"] = " ".join(a.note) if a.note else ""
    side_save(side)
    print("next write starts a fresh update session%s" % ((" — “" + side["pending_note"] + "”") if side["pending_note"] else ""))

def cmd_end(a):
    side = side_load(); side["session"] = None; side["session_at"] = None; side_save(side)
    print("session closed.")

FIELDS = [("title", "title"), ("note", "note"), ("detail", "detail")]

def cmd_set(a):
    def go(state):
        nd = need(state, a.id); n = nd["node"]; touched = []
        if nd["kind"] != "item": sys.exit("%s is a %s — use rel-set / note-set for that." % (a.id, nd["kind"]))
        for arg, key in FIELDS:
            v = getattr(a, arg)
            if v is not None and n.get(key) != v: n[key] = v; touched.append(key)
        if a.done and not n.get("done"): n["done"] = True; touched.append("done")
        if a.undone and n.get("done"): n["done"] = False; touched.append("done")
        if a.pts is not None and n.get("pts") != a.pts: n["pts"] = a.pts; touched.append("pts")
        if a.no_pts and "pts" in n: del n["pts"]; touched.append("pts")
        kind = "edit"
        if a.section and nd["section"] != a.section:
            dest = sec_by_id(state, a.section)
            if not dest: sys.exit("no section %r" % a.section)
            src = sec_by_id(state, nd["section"])
            src["items"] = [i for i in src["items"] if i["id"] != a.id]
            dest.setdefault("items", []).append(n)
            touched.append("section"); kind = "move"; nd["section"] = a.section
        if not touched: return [], "no change — every field already had that value."
        stamp(n)
        return ([{"id": a.id, "title": n.get("title", a.id), "kind": kind,
                  "section": nd["section"], "fields": sorted(set(touched))}],
                "%s %s  (%s)" % (kind, a.id, ", ".join(sorted(set(touched)))))
    print(transaction(go))

def cmd_add(a):
    def go(state):
        sec = sec_by_id(state, a.section)
        if not sec: sys.exit("no section %r — see: roadmap.py sections" % a.section)
        it = {"id": newid(), "title": a.title}
        if a.note: it["note"] = a.note
        if a.detail: it["detail"] = a.detail
        if a.pts is not None: it["pts"] = a.pts
        it["done"] = False
        stamp(it)
        items = sec.setdefault("items", [])
        pos = len(items)
        if a.after:
            j = next((k for k, x in enumerate(items) if x["id"] == a.after), None)
            if j is not None: pos = j + 1
        items.insert(pos, it)
        return ([{"id": it["id"], "title": it["title"], "kind": "add", "section": a.section, "fields": []}],
                "added %s → %s  (%s)" % (it["id"], a.section, it["title"]))
    print(transaction(go))

def cmd_rm(a):
    def go(state):
        nd = need(state, a.id); n = nd["node"]
        if nd["kind"] != "item": sys.exit("rm only handles items; use the browser for releases/notes.")
        sec = sec_by_id(state, nd["section"])
        sec["items"] = [i for i in sec["items"] if i["id"] != a.id]
        state.setdefault("trash", []).insert(0, {"kind": "item", "payload": n, "from": nd["section"], "at": now_iso()})
        return ([{"id": a.id, "title": n.get("title", a.id), "kind": "delete", "section": nd["section"], "fields": []}],
                "trashed %s  (%s)" % (a.id, n.get("title", "")))
    print(transaction(go))

def cmd_rel_set(a):
    def go(state):
        nd = need(state, a.id); n = nd["node"]
        if nd["kind"] != "release": sys.exit("%s is not a release" % a.id)
        touched = []
        for k in ("title", "status", "sub"):
            v = getattr(a, k)
            if v is not None and n.get(k) != v: n[k] = v; touched.append(k)
        if not touched: return [], "no change."
        stamp(n)
        return ([{"id": a.id, "title": n.get("title", a.id), "kind": "edit", "section": None, "fields": touched}],
                "edited release %s  (%s)" % (a.id, ", ".join(touched)))
    print(transaction(go))

def cmd_rel_add(a):
    def go(state):
        r = {"id": newid("r"), "title": a.title, "status": a.status, "sub": a.sub or "", "open": True, "items": []}
        stamp(r)
        state["releases"].insert(0, r)
        return ([{"id": r["id"], "title": r["title"], "kind": "add", "section": None, "fields": []}],
                "added release %s  (%s)" % (r["id"], r["title"]))
    print(transaction(go))

def cmd_note_add(a):
    def go(state):
        n = {"id": newid("n"), "title": a.title, "html": a.html, "open": True}
        stamp(n)
        state.setdefault("notes", []).append(n)
        return ([{"id": n["id"], "title": n["title"], "kind": "add", "section": None, "fields": []}],
                "added note %s  (%s)" % (n["id"], n["title"]))
    print(transaction(go))

def cmd_note_set(a):
    def go(state):
        nd = need(state, a.id); n = nd["node"]
        if nd["kind"] != "note": sys.exit("%s is not a note" % a.id)
        touched = []
        for k in ("title", "html"):
            v = getattr(a, k)
            if v is not None and n.get(k) != v: n[k] = v; touched.append(k)
        if not touched: return [], "no change."
        stamp(n)
        return ([{"id": a.id, "title": n.get("title", a.id), "kind": "edit", "section": None, "fields": touched}],
                "edited note %s  (%s)" % (a.id, ", ".join(touched)))
    print(transaction(go))

def num_arg(s):
    return num(float(s))

def main():
    p = argparse.ArgumentParser(prog="roadmap.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--file", default=DATA, help="path to roadmap-data.json (default: next to this script, or $ROADMAP_FILE)")
    sub = p.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("init", help="create a fresh roadmap-data.json"); q.set_defaults(fn=cmd_init)
    q.add_argument("--project", help="project name shown in the page header")
    q.add_argument("--agent", help="what to call the agent in the UI, e.g. Claude")
    q.add_argument("--demo", action="store_true", help="start from the example roadmap instead of an empty one")
    q.add_argument("--force", action="store_true")

    sub.add_parser("status").set_defaults(fn=cmd_status)
    sub.add_parser("sections").set_defaults(fn=cmd_sections)
    sub.add_parser("seen").set_defaults(fn=cmd_seen)
    sub.add_parser("end").set_defaults(fn=cmd_end)

    q = sub.add_parser("ls"); q.set_defaults(fn=cmd_ls)
    q.add_argument("--section"); q.add_argument("--grep")
    q.add_argument("--todo", action="store_true"); q.add_argument("--done", action="store_true")
    q.add_argument("--by", choices=["human", "agent"])

    q = sub.add_parser("show"); q.set_defaults(fn=cmd_show); q.add_argument("id")

    q = sub.add_parser("changes"); q.set_defaults(fn=cmd_changes)
    q.add_argument("--by", choices=["human", "agent"])
    q.add_argument("--since", default="last", help="last | ISO timestamp | 12h | 3d")
    q.add_argument("--mark", action="store_true", help="move the watermark to now afterwards")

    q = sub.add_parser("begin"); q.set_defaults(fn=cmd_begin); q.add_argument("note", nargs="*")

    q = sub.add_parser("set"); q.set_defaults(fn=cmd_set); q.add_argument("id")
    q.add_argument("--title"); q.add_argument("--note"); q.add_argument("--detail"); q.add_argument("--section")
    q.add_argument("--done", action="store_true"); q.add_argument("--undone", action="store_true")
    q.add_argument("--pts", type=num_arg); q.add_argument("--no-pts", action="store_true")

    q = sub.add_parser("add"); q.set_defaults(fn=cmd_add)
    q.add_argument("--section", required=True); q.add_argument("--title", required=True)
    q.add_argument("--note"); q.add_argument("--detail"); q.add_argument("--pts", type=num_arg); q.add_argument("--after")

    q = sub.add_parser("rm"); q.set_defaults(fn=cmd_rm); q.add_argument("id")

    q = sub.add_parser("rel-set"); q.set_defaults(fn=cmd_rel_set); q.add_argument("id")
    q.add_argument("--title"); q.add_argument("--sub")
    q.add_argument("--status", choices=["planned", "inprogress", "submitted", "released"])

    q = sub.add_parser("rel-add"); q.set_defaults(fn=cmd_rel_add); q.add_argument("--title", required=True)
    q.add_argument("--sub"); q.add_argument("--status", default="planned",
                                            choices=["planned", "inprogress", "submitted", "released"])

    q = sub.add_parser("note-add"); q.set_defaults(fn=cmd_note_add)
    q.add_argument("--title", required=True); q.add_argument("--html", required=True)

    q = sub.add_parser("note-set"); q.set_defaults(fn=cmd_note_set); q.add_argument("id")
    q.add_argument("--title"); q.add_argument("--html")

    a = p.parse_args()
    set_paths(a.file)
    a.fn(a)

if __name__ == "__main__":
    main()
