# /// script
# dependencies = ["requests"]
# ///
"""Move "Data Marts + Semantic Layer" rows off table tasks onto each dashboard's PR tasks.

  uv run --with requests python scripts/asana_migrate.py --section "1 · Assessments"           # preview
  uv run --with requests python scripts/asana_migrate.py --section "1 · Assessments" --apply   # make the changes
  uv run --with requests python scripts/asana_migrate.py                                       # whole project

A one-time move to the layout in docs/superpowers/specs/2026-11-23-asana-dashboard-build-plans-design.md.
Needs ASANA_PAT, your own personal access token, as scripts/asana_sync.py does. Run asana_sync.py after
--apply so each moved row gets its status from its new parent.

For each row on a table task (a subtask with a `Used by:` line of dashboard links, other than a `mart:` /
`cube:` / `view:` stage):
  - its owner is the earliest-due dashboard its `Used by:` names; a dashboard with no due date sorts last,
    and a tie goes to the older dashboard task. A row whose owner is outside --section stays put.
  - a done row stays on its table and closes with it; an open row whose notes have a line starting
    `Deferred:` moves directly under the owner dashboard.
  - an open row moves under the owner's PR task for that table: an open `PR (dbt|Cube): ...` subtask that
    names the table after its ` · ` (the Cube PR when both do), else a new
    `PR (dbt|Cube): open fields · <table>`, dbt when the table has an open `mart:` stage, its notes say
    "New mart", or one of the rows carries needs-data. A new PR task has no due date. Its links to the
    table's stages are removed.
Another dashboard that uses the same row gets nothing: the builder's inventory finds shared work. A table
the run moves no row off is left alone, unless it is in the run (the whole project, or --section's own
tables) and nothing is open on it: then it closes, or is reported when an open stage is all that is left.
On a table it does touch, an open subtask with no `Used by:` line stays put and is reported. Once nothing
open is left on a table, its open stages close (or are reported when no PR took its work) and the table
task closes.
"""

import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = re.compile(r"^(mart|cube|view):")
DEFERRED = re.compile(r"^\s*Deferred:", re.M)
GID = re.compile(r"\b(\d{16})\b")


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "asana_sync", os.path.join(HERE, "asana_sync.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load scripts/asana_sync.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["asana_sync"] = module
    spec.loader.exec_module(module)
    return module


sync = _load_sync()


# ---------------------------------------------------------------- pure planning
def stage_kind(name):
    m = STAGE.match(name or "")
    return m.group(1) if m else None


def used_by(task):
    m = sync.USED_BY.search(task.get("notes") or "")
    return set(GID.findall(m.group(1))) if m else set()


def _tags(task):
    return {t["name"].lower() for t in task.get("tags") or []}


def pr_tables(name):
    """The tables a PR task names after its last ` · `, e.g. `PR (dbt): grade fields · dim_a, dim_b`."""
    if " · " not in name:
        return []
    return [x.strip() for x in name.rsplit(" · ", 1)[1].split(",") if x.strip()]


def owner_of(gids, by_gid):
    """The earliest-due dashboard among gids; no due date sorts last, a tie goes to the older task."""
    known = [by_gid[g] for g in gids if g in by_gid]
    if not known:
        return None
    return min(known, key=lambda d: (d.get("due_on") or "9999-12-31", int(d["gid"])))[
        "gid"
    ]


def plan(dashboards, tables, children_of, scope, section=None):
    """The ordered actions that move every in-scope row off its table task.

    dashboards: [{gid, name, due_on}]; tables: [{gid, name, notes, subtasks}]; children_of: dashboard gid ->
    its subtasks [{gid, name}]; scope: a set of dashboard gids, or None for all. Returns dicts with an `op`
    of create, move, unlink, close or report. A `new:<key>` reference names a task a create makes.
    """
    by_gid = {d["gid"]: d for d in dashboards}

    def in_scope(g):
        return scope is None or g in scope

    creates, moves, unlinks, closes, reports = {}, [], [], [], []

    for t in tables:
        subs = t["subtasks"]
        stages = [s for s in subs if stage_kind(s["name"])]
        stage_gids = {s["gid"] for s in stages}
        left = []  # names of what stays on the table
        unclaimed = []  # open subtasks no dashboard claims: reported if the run touches the table
        touched = False  # the run moves at least 1 row off this table
        open_by_owner = {}
        for s in subs:
            if s["gid"] in stage_gids or s.get("completed"):
                continue  # a done row stays on its table and closes with it
            dashes = used_by(s) & by_gid.keys()
            if not dashes:
                left.append(s["name"])
                unclaimed.append(s["name"])
                continue
            owner = owner_of(dashes, by_gid)
            if not in_scope(owner):
                left.append(s["name"])
                continue
            touched = True
            if DEFERRED.search(s.get("notes") or ""):
                moves.append(
                    {"op": "move", "task": s["gid"], "parent": owner, "name": s["name"]}
                )
            else:
                open_by_owner.setdefault(owner, []).append(s)
            deps = [
                d["gid"] for d in s.get("dependencies") or [] if d["gid"] in stage_gids
            ]
            if deps:
                unlinks.append({"op": "unlink", "task": s["gid"], "deps": deps})

        pr_refs = []
        for owner, rows in open_by_owner.items():
            # a row sits under the PR that ships its Cube member: the Cube PR when a dbt PR comes first
            named = [
                c
                for c in children_of.get(owner, [])
                if not c.get("completed")
                and sync.pr_type(c["name"])
                and t["name"] in pr_tables(c["name"])
            ]
            found = next(
                (c for c in named if sync.pr_type(c["name"]) == "cube"),
                named[0] if named else None,
            )
            if found:
                ref = found["gid"]
            else:
                dbt = (
                    any(
                        stage_kind(s["name"]) == "mart" and not s.get("completed")
                        for s in stages
                    )
                    or "new mart" in (t.get("notes") or "").lower()
                    or any("needs-data" in _tags(r) for r in rows)
                )
                key = f"pr:{owner}:{t['gid']}"
                creates[key] = {
                    "op": "create",
                    "key": key,
                    "parent": owner,
                    "name": f"PR ({'dbt' if dbt else 'Cube'}): open fields · {t['name']}",
                    "notes": f"The open work on {t['name']} that {by_gid[owner]['name']} needs first. "
                    "The rows below are the fields it ships.",
                }
                ref = f"new:{key}"
            pr_refs.append(ref)
            for r in rows:
                moves.append(
                    {"op": "move", "task": r["gid"], "parent": ref, "name": r["name"]}
                )

        if not touched:
            # a table emptied by hand closes; one with open stages but no rows is reported
            in_run = scope is None or any(
                (m.get("section") or {}).get("name") == section
                for m in t.get("memberships") or []
            )
            open_stages = [s["name"] for s in stages if not s.get("completed")]
            if in_run and not left and not t.get("completed"):
                if open_stages:
                    reports.append(
                        {
                            "op": "report",
                            "text": f"{t['name']}: no rows left; open stages: "
                            + ", ".join(open_stages),
                        }
                    )
                else:
                    closes.append(
                        {
                            "op": "close",
                            "task": t["gid"],
                            "name": t["name"],
                            "comment": "Closed by asana_migrate: nothing is left on this table.",
                        }
                    )
            continue  # otherwise a table this run leaves alone gets no reports and no closes
        reports += [
            {"op": "report", "text": f"{t['name']}: left on the table: {name}"}
            for name in unclaimed
        ]
        if left:
            continue  # stages stay open while anything is left on the table
        for s in stages:
            if s.get("completed"):
                continue
            if pr_refs:
                closes.append(
                    {
                        "op": "close",
                        "task": s["gid"],
                        "name": s["name"],
                        "comment": f"Closed by asana_migrate: the open work on {t['name']} is "
                        "now planned as its PR task under the dashboard that needs it first.",
                    }
                )
            else:
                left.append(s["name"])
                reports.append(
                    {
                        "op": "report",
                        "text": f"{t['name']}: open stage with no PR to take it: {s['name']}",
                    }
                )
        if not left and not t.get("completed"):
            closes.append(
                {
                    "op": "close",
                    "task": t["gid"],
                    "name": t["name"],
                    "comment": "Closed by asana_migrate: every open row now sits under the PR task "
                    "or the dashboard that needs it first.",
                }
            )

    return list(creates.values()) + moves + unlinks + closes + reports


# ---------------------------------------------------------------- apply
def run(actions, apply):
    made = {}

    def res(ref):
        return made.get(ref[4:], ref) if ref.startswith("new:") else ref

    for a in actions:
        op = a["op"]
        if op == "report":
            print(f"  report: {a['text']}")
            continue
        if op == "create":
            desc = f"create '{a['name']}' under {a['parent']}"
        elif op == "move":
            desc = f"move '{a['name']}' under {a['parent']}"
        elif op == "unlink":
            desc = f"{a['task']}: remove stage links {', '.join(a['deps'])}"
        else:
            desc = f"close '{a['name']}'"
        print(("  " if apply else "  would: ") + desc)
        if not apply:
            continue
        if op == "create":
            data = {"name": a["name"], "notes": a["notes"]}
            made[a["key"]] = sync.call(
                "POST", f"/tasks/{res(a['parent'])}/subtasks", data
            )["data"]["gid"]
        elif op == "move":
            sync.call(
                "POST", f"/tasks/{a['task']}/setParent", {"parent": res(a["parent"])}
            )
        elif op == "unlink":
            sync.call(
                "POST",
                f"/tasks/{a['task']}/removeDependencies",
                {"dependencies": a["deps"]},
            )
        elif op == "close":
            sync.call("PUT", f"/tasks/{a['task']}", {"completed": True})
            sync.call("POST", f"/tasks/{a['task']}/stories", {"text": a["comment"]})


def main(argv):
    apply = "--apply" in argv
    section = argv[argv.index("--section") + 1] if "--section" in argv[:-1] else None
    token = (os.environ.get("ASANA_PAT") or "").strip()
    if not token:
        sys.exit("Set ASANA_PAT first: read -rs ASANA_PAT && export ASANA_PAT")
    sync.connect(token)

    top = sync.get_all(
        f"/projects/{sync.PROJECT}/tasks",
        {
            "opt_fields": "name,notes,completed,due_on,tags.name,memberships.section.name"
        },
    )
    dashboards = [
        {"gid": t["gid"], "name": t["name"], "due_on": t.get("due_on")}
        for t in top
        if "dashboard" in _tags(t)
    ]
    scope = set(sync.dashboards_in_section(top, section)) if section else None
    if scope == set():
        sys.exit(f"--section {section!r} holds no task tagged 'dashboard'.")
    tables = [
        dict(
            t,
            subtasks=sync.get_all(
                f"/tasks/{t['gid']}/subtasks", {"opt_fields": sync.FIELDS}
            ),
        )
        for t in top
        if sync.TABLE.match(t["name"])
    ]
    children_of = {
        d["gid"]: sync.get_all(
            f"/tasks/{d['gid']}/subtasks", {"opt_fields": "name,completed"}
        )
        for d in dashboards
        if scope is None or d["gid"] in scope
    }
    actions = plan(dashboards, tables, children_of, scope, section)
    counts = {}
    for a in actions:
        counts[a["op"]] = counts.get(a["op"], 0) + 1
    print(
        f"Plan for {section or 'the whole project'}: "
        + ", ".join(f"{n} {op}" for op, n in sorted(counts.items()))
    )
    run(actions, apply)
    if not apply:
        print(
            "\nPreview only. Re-run with --apply to make these changes, then run asana_sync.py."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
