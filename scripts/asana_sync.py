# /// script
# dependencies = ["requests"]
# ///
"""Keep "Data Marts + Semantic Layer" in sync with its dependencies and with what ships in Cube.

  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid>          # preview, changes nothing
  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid> --apply  # make the changes
  uv run --with requests python scripts/asana_sync.py --section "1 · Assessments"          # one project section

--only limits the run to one dashboard task's measure and dimension rows and skips step 1, so a validation
changes nothing else; the cube builder uses it, one dashboard at a time. --section does the same for every
dashboard in one project section. With neither, the run covers every dashboard. Run it from a teamster
checkout: it runs `git fetch` and reads src/cube/model on origin/main.

Needs ASANA_PAT, your own personal access token, in the environment for both modes. Create one in Asana's
developer console (app.asana.com/0/my-apps), then load it without echoing it or saving it to history:
  read -rs ASANA_PAT && export ASANA_PAT

Dashboards are the project's top-level tasks tagged `dashboard`. Rows are:
  - a dashboard task's measure subtasks (tagged `measure`, or notes carrying a `Status:` line);
  - an untagged subtask of a dashboard task whose notes carry a `Used by:` line (a deferred row): a dimension;
  - rows tagged `measure` or `dimension` under a dashboard's PR tasks (`PR (dbt|Cube): <what> · <table>`, or a synced
    `#NNNN | <type>(<scope>): ...` task). With no stage blockers left, such a row's status comes from its
    parent: needs-data while the parent is an open dbt PR or an open dbt PR blocks it, needs-cube otherwise.
    An untagged subtask there whose notes carry a `Used by:` line is tagged `dimension`; any other untagged
    subtask there is a work item, not a row;
  - dimension rows: subtasks of table tasks, other than `mart:` / `cube:` / `view:` stages, whose notes carry
    a `Used by:` line of dashboard task links. One dimension row lives on the table its column comes from.
Each run:
  1. Chains stages inside every table task: `mart:` blocks `cube:`, `cube:` blocks `view:` (adds only missing links).
     It never links table tasks to dashboards: a dashboard is blocked by its own PR tasks.
  2. Ticks a row done when it is live in Cube: every Cube member its notes name is on a public view on main, and
     no blocker on the row is open. Validation does not gate done. A row blocks only on the stage or addition that
     builds its own member: a cut belongs on its dimension row, so the report lists rows whose members are on main
     but a blocker is open. Every other done row is unticked, with the reason in the report.
  3. Gives each open row at most one status tag; done rows carry none:
       an open mart stage or column addition -> needs-data
       otherwise an open cube / view stage   -> needs-cube
       otherwise a `Needs: data` / `Needs: cube` line in the notes, the triage for a row nobody has made a task for
       otherwise                              -> none (nobody has worked out what it needs yet)
  4. Tags every row `measure` or `dimension` (drops the duplicate workspace `measure` tag).
  5. Reads ~/asana-sync/validation/latest.json (the cube-dashboard skill's latest verdict per row): 'validated'
     when the latest verdict is pass, removed otherwise. The report lists every other verdict; its gaps belong
     in subtasks under the row, never in a tag. With no file, the run skips this step and leaves every
     'validated' tag as it is: a missing file is no verdicts, not failed ones.
  6. Strips the tags in OLD_TAGS from every row.
"""

import json
import os
import re
import subprocess
import sys
import time

API = "https://app.asana.com/api/1.0"
PROJECT = "1213735218595734"
WORKSPACE = "913513768672"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEASURE_TAG, DUP_MEASURE_TAG = "1214073246940451", "1215598455588323"
DASHBOARD_TAG = "dashboard"
KINDS = ("measure", "dimension")
# At most one on an open row, from its open blockers; done rows carry none.
STATUS = ["needs-data", "needs-cube"]
VALIDATED = "validated"  # the latest validation found Cube equal to the dashboard
DIMENSION = "dimension"  # on each dimension row, as `measure` is on measure rows
# No rule sets these; the sync strips them so a row carries only STATUS, VALIDATED and its kind tag.
OLD_TAGS = [
    "cube-covered",
    "cube-partial",
    "mart-ready",
    "mart-missing",
    "untriaged",
    "matched",
    "mismatch",
    "unvalidated",
]
LATEST = "~/asana-sync/validation/latest.json"
TABLE = re.compile(r"^(dim|fct|bridge)_[a-z0-9_]+$")
FIELDS = "name,completed,notes,tags.name,tags.gid,dependencies.gid,parent.name"
ROWF = "name,completed,notes,tags.name,tags.gid,dependencies"
USED_BY = re.compile(r"^\s*Used by:\s*(.*)$", re.M)
NEEDS = re.compile(r"^\s*Needs:\s*(cube|data)\b", re.M | re.I)

# Run state. main() sets these; the helpers below read them.
APPLY = False
ONLY = None
s = None
changes = []
validation = None
shipped, cube_members = set(), set()
status_gid, kind_gid, old_gid = {}, {}, {}
validated_gid = None
stage_map = {}
report_ticked, report_untick, report_unverified = [], [], []
report_blocked_on_main, report_gaps = [], []


# ---------------------------------------------------------------- pure helpers
def load_validation(path):
    """The validation rows by task gid, or None when the file is missing."""
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["rows"]


def _tag_names(task):
    return {t["name"].lower() for t in task.get("tags") or []}


def dashboard_gids(tasks):
    """Gids of the tasks tagged `dashboard`, in the order given."""
    return [t["gid"] for t in tasks if DASHBOARD_TAG in _tag_names(t)]


def dashboards_in_section(tasks, section):
    """Gids of the dashboards in the named project section; every dashboard when section is None."""
    return [
        t["gid"]
        for t in tasks
        if DASHBOARD_TAG in _tag_names(t)
        and (
            section is None
            or any(
                (m.get("section") or {}).get("name") == section
                for m in t.get("memberships") or []
            )
        )
    ]


def row_kind(task):
    """'measure' or 'dimension' from the task's tags, else None."""
    names = _tag_names(task)
    return next((k for k in KINDS if k in names), None)


def want_status(*, live, stage_blockers, needs_line):
    """The status tag for a row whose blockers are table stages.

    A blocker outranks the notes' `Needs:` line; done blockers count for nothing.
    """
    if live:
        return None
    open_blockers = [b for b in stage_blockers if not b.get("completed")]
    if any(b["kind"] in ("mart", "addition") for b in open_blockers):
        return "needs-data"
    if open_blockers:
        return "needs-cube"
    if needs_line:
        return f"needs-{needs_line.lower()}"
    return None


PR_BRACKET = re.compile(r"\((dbt|cube)\)", re.I)
SYNCED_SCOPE = re.compile(r"^#\d+\s*\|\s*\w+\(([^)]*)\)")


def pr_type(name):
    """'dbt' or 'cube' for a PR task, from `(dbt)` / `(Cube)` or a synced task's commit scope.

    A synced `#NNNN | feat(dbt,cube): ...` PR changes the data first, so dbt wins when both appear.
    """
    if m := PR_BRACKET.search(name or ""):
        return m.group(1).lower()
    if m := SYNCED_SCOPE.match(name or ""):
        scopes = {x.strip().lower() for x in m.group(1).split(",")}
        if "dbt" in scopes:
            return "dbt"
        if "cube" in scopes:
            return "cube"
    return None


def rows_under(dashboard, children, grandchildren):
    """Rows under one dashboard task, each with its parent, and the untagged tasks that look like rows.

    A row is a task tagged `measure` or `dimension`: a direct subtask of the dashboard (parent None) or a
    subtask of a PR task or other work item under it (parent = that subtask). An untagged subtask
    there whose notes carry a `Used by:` line is a row too, a dimension, as on a table task. Table tasks
    under a dashboard keep their own path. Any other untagged subtask of a PR task is reported: without
    its kind tag it drops off the status page.
    """
    rows, untagged = [], []
    for c in children:
        if TABLE.match(c["name"]):
            continue
        if row_kind(c):
            rows.append((c, None))
            continue
        kids = grandchildren.get(c["gid"], [])
        for g in kids:
            if row_kind(g) or USED_BY.search(g.get("notes") or ""):
                rows.append((g, c))
            elif pr_type(c["name"]):
                untagged.append(g)
    return rows, untagged


def direct_rows(children):
    """A dashboard's own rows, each with its kind: tagged, a legacy measure with a `Status:` line, or an
    untagged subtask with a `Used by:` line (a deferred row), which is a dimension. Table and PR tasks are not rows.
    """
    out = []
    for r in children:
        notes = r.get("notes") or ""
        if TABLE.match(r["name"]) or pr_type(r["name"]):
            continue
        if kind := row_kind(r):
            out.append((r, kind))
        elif "Status:" in notes:
            out.append((r, "measure"))
        elif USED_BY.search(notes):
            out.append((r, "dimension"))
    return out


def want_status_pr(*, live, parent, parent_blockers):
    """The status tag for a row under a PR task.

    needs-data while the parent is an open dbt PR or an open dbt PR blocks it; otherwise needs-cube, including
    a merged parent whose members are not on a public view yet.
    """
    if live:
        return None
    if pr_type(parent["name"]) == "dbt" and not parent.get("completed"):
        return "needs-data"
    if any(
        pr_type(b["name"]) == "dbt" and not b.get("completed") for b in parent_blockers
    ):
        return "needs-data"
    return "needs-cube"


def view_includes(yml):
    """(include name, exposed name) for each member of one view file.

    A `prefix: true` join exposes `<cube>_<member>` (the last join_path cube); an include is a bare name or the
    dict form `- name: <member>`. Notes may name either form, so both count.
    """
    out, cube, prefix = [], None, False
    for line in yml.splitlines():
        if m := re.match(r"^\s{6}- join_path:\s*(\S+)", line):
            cube, prefix = m.group(1).split(".")[-1], False
        elif re.match(r"^\s{8}prefix:\s*true\s*$", line):
            prefix = True
        elif m := re.match(r"^\s{10}-\s+(?:name:\s*)?([a-z0-9_]+)\s*$", line):
            out.append(
                (m.group(1), f"{cube}_{m.group(1)}" if prefix and cube else m.group(1))
            )
    return out


def members_named(notes):
    m = re.search(
        r"Where it lives:\s*(.*?)(?:\n\s*(?:Regions|Was|Needs|Use):|\n\s*https?://|$)",
        notes or "",
        re.S,
    )
    # Some shipped rows name their member only in the Status line ("Status: cube-covered
    # (shipped: pct_tier_1_2 on ..._view)"), with no "Where it lives:" line or one that says
    # "same as above". Read it only when it says cube-covered: a mart-ready Status line
    # names the inputs the row still needs built, not a shipped member.
    status = re.search(r"Status:\s*cube-covered([^\n]*)", notes or "")
    text = " ".join(x.group(1) for x in (m, status) if x)
    toks = set(
        re.findall(
            r"\b([a-z][a-z0-9_]*\.[a-z][a-z0-9_]+|[a-z][a-z0-9]+(?:_[a-z0-9]+)+)\b",
            text,
        )
    )
    return {
        x
        for x in toks
        if not TABLE.match(x.split(".")[-1])
        and not x.startswith(("int_", "stg_", "rpt_", "base_"))
    }


def member(x):
    """Notes name members by cube or by view; compare the member part."""
    return x.split(".")[-1]


# ---------------------------------------------------------------- Asana and git
def connect(token):
    """Open the Asana session that call() and get_all() use."""
    global s
    import requests

    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})


def call(method, path, data=None, params=None):
    if s is None:
        raise RuntimeError("main() opens the session before any call")
    for attempt in range(6):
        r = s.request(
            method,
            API + path,
            json={"data": data} if data is not None else None,
            params=params,
        )
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(int(r.headers.get("Retry-After", 2**attempt)))
            continue
        if r.status_code >= 400:
            sys.exit(f"{method} {path} -> {r.status_code}: {r.text[:400]}")
        return r.json()
    sys.exit(f"{method} {path}: gave up after retries")


def get_all(path, params):
    out, offset = [], None
    while True:
        p = dict(params, limit=100, **({"offset": offset} if offset else {}))
        r = call("GET", path, params=p)
        out += r.get("data", [])
        offset = (r.get("next_page") or {}).get("offset")
        if not offset:
            return out


def write(desc, method, path, data):
    changes.append(desc)
    print(("  " if APPLY else "  would: ") + desc)
    if APPLY:
        call(method, path, data)
        time.sleep(0.1)


def git(*args):
    # trunk-ignore(bandit/B603,bandit/B607): hardcoded git command, no user input
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, check=False
    ).stdout


def ensure_tag(name):
    """Create a missing tag on --apply; in preview, return a placeholder and say so."""
    if not APPLY:
        print(f"  would: create tag '{name}'")
        return f"new:{name}"
    # call() wraps the payload in {"data": ...} itself.
    return call("POST", "/tags", {"name": name, "workspace": WORKSPACE})["data"]["gid"]


# ---------------------------------------------------------------- one row
def sync_row(r, kind, parent=None, parent_blockers=()):
    """Steps 2-6 for one measure row or one dimension row.

    A row under a PR task (parent given) takes its status from that parent while it has no
    stage blockers left; a row still linked to table stages keeps the stage rule.
    """
    notes = r.get("notes") or ""
    rid, name = r["gid"], f"[{kind}] {r['name'][:64]}"
    have = {t["gid"] for t in r.get("tags", [])}
    # 4. the row's own kind tag
    if kind == "measure" and DUP_MEASURE_TAG in have:
        write(
            f"{name}: duplicate 'measure' tag -> project 'measure' tag",
            "POST",
            f"/tasks/{rid}/removeTag",
            {"tag": DUP_MEASURE_TAG},
        )
    if kind_gid[kind] not in have:
        write(
            f"{name}: add '{kind}' tag",
            "POST",
            f"/tasks/{rid}/addTag",
            {"tag": kind_gid[kind]},
        )
    deps = r.get("dependencies")
    if deps is None:
        deps = get_all(f"/tasks/{rid}/dependencies", {"opt_fields": "name"})
    blockers = [stage_map[d["gid"]] for d in deps if d["gid"] in stage_map]
    open_blockers = [b for b in blockers if not b.get("completed")]
    done = r["completed"]
    cube_named = {
        x for x in members_named(notes) if member(x) in cube_members
    }  # only real Cube measure/dimension names
    on_main = bool(cube_named) and all(member(x) in shipped for x in cube_named)
    live = on_main and not open_blockers
    # 5. validation results from the cube-dashboard skill; skipped with no validation file
    if validation is not None:
        verdict = validation.get(rid, {}).get("verdict")
        if verdict == "pass" and validated_gid not in have:
            write(
                f"{name}: latest validation passed -> add '{VALIDATED}'",
                "POST",
                f"/tasks/{rid}/addTag",
                {"tag": validated_gid},
            )
        elif verdict != "pass" and validated_gid in have:
            write(
                f"{name}: latest validation {verdict or 'never run'} -> remove '{VALIDATED}'",
                "POST",
                f"/tasks/{rid}/removeTag",
                {"tag": validated_gid},
            )
        if verdict and verdict != "pass":
            report_gaps.append(f"{name} ({rid}): {verdict}")
    # 2. done means it is live in Cube
    if live and not done:
        write(
            f"{name}: live in Cube -> tick done",
            "PUT",
            f"/tasks/{rid}",
            {"completed": True},
        )
        report_ticked.append(f"{name} ({rid})")
    elif done and not live:
        why = []
        if open_blockers:
            why.append(
                f"open blocker: {'; '.join(b['name'][:60] for b in open_blockers)}"
            )
        if not on_main:
            gone = sorted(x for x in cube_named if member(x) not in shipped)
            why.append(
                f"not on main: {', '.join(gone)}"
                if gone
                else "its notes name no member Cube defines on main"
            )
        write(
            f"{name}: {'; '.join(why)} -> untick",
            "PUT",
            f"/tasks/{rid}",
            {"completed": False},
        )
        report_untick.append(f"{name} ({rid}): {'; '.join(why)}")
    if on_main and open_blockers:
        report_blocked_on_main.append(
            f"{name} ({rid}): {'; '.join(b['name'][:60] for b in open_blockers)}"
        )
    if blockers and not open_blockers and not on_main:
        report_unverified.append(
            f"{name} ({rid}): blockers done, but Cube member(s) not found on main: {', '.join(sorted(cube_named)) or 'none named'}"
        )
    # 3. status tag: what an open row still needs; a blocker outranks the notes' `Needs:` line
    needs = NEEDS.search(notes)
    if parent is not None and not blockers:
        want = want_status_pr(
            live=live, parent=parent, parent_blockers=list(parent_blockers)
        )
    else:
        want = want_status(
            live=live,
            stage_blockers=blockers,
            needs_line=needs.group(1) if needs else None,
        )
    for n in STATUS:
        if n != want and status_gid[n] in have:
            write(
                f"{name}: remove '{n}'",
                "POST",
                f"/tasks/{rid}/removeTag",
                {"tag": status_gid[n]},
            )
    if want and status_gid[want] not in have:
        write(
            f"{name}: add '{want}'",
            "POST",
            f"/tasks/{rid}/addTag",
            {"tag": status_gid[want]},
        )
    # 6. tags no rule sets
    for gid in sorted(have & old_gid.keys()):
        write(
            f"{name}: remove old tag '{old_gid[gid]}'",
            "POST",
            f"/tasks/{rid}/removeTag",
            {"tag": gid},
        )


# ---------------------------------------------------------------- the run
def main(argv):
    global APPLY, ONLY, validation, validated_gid

    APPLY = "--apply" in argv
    ONLY = argv[argv.index("--only") + 1] if "--only" in argv[:-1] else None
    section_name = (
        argv[argv.index("--section") + 1] if "--section" in argv[:-1] else None
    )
    if ONLY and section_name:
        sys.exit("Pass --only or --section, not both.")

    validation = load_validation(LATEST)
    if validation is None:
        print(f"No {LATEST}: step 5 skipped, 'validated' tags left alone.")

    token = (os.environ.get("ASANA_PAT") or "").strip()
    if not token:
        sys.exit("Set ASANA_PAT first: read -rs ASANA_PAT && export ASANA_PAT")
    connect(token)

    # ------------------------------------------------------------ shipped Cube members on main
    git("fetch", "origin", "main", "-q")
    views = git(
        "ls-tree", "-r", "--name-only", "origin/main", "src/cube/model/views"
    ).split()
    exposed = set()
    for v in views:
        if v.endswith(".yml"):
            y = git("show", f"origin/main:{v}")
            vname = os.path.basename(v)[:-4]
            for raw, name in view_includes(y):
                shipped.update({raw, f"{vname}.{raw}", name, f"{vname}.{name}"})
                exposed.add(name)
    if not shipped:
        # an empty read would untick every done row as "not on main"
        sys.exit(
            "Read no Cube view files on origin/main (src/cube/model/views): stopping before any change."
        )
    print(
        f"Cube members on public views (origin/main): {len([x for x in shipped if '.' in x])}"
    )
    # every measure / dimension name defined in any cube (public or not): a word only counts as a Cube member if it's here
    for c in git(
        "ls-tree", "-r", "--name-only", "origin/main", "src/cube/model/cubes"
    ).split():
        if c.endswith(".yml"):
            section = None
            for line in git("show", f"origin/main:{c}").splitlines():
                if re.match(r"^\s{4}[a-z_]+:\s*$", line):
                    section = line.strip()[:-1]
                m = re.match(r"^\s{6}-\s+name:\s*([a-z][a-z0-9_]*)\s*$", line)
                if m and section in ("measures", "dimensions"):
                    cube_members.add(m.group(1))
    cube_members.update(
        exposed  # a prefixed view name (`locations_location_name`) is a member too
    )

    # ------------------------------------------------------------ tags by name
    tags = {}
    for t in get_all(f"/workspaces/{WORKSPACE}/tags", {"opt_fields": "name"}):
        tags.setdefault(t["name"], []).append(t["gid"])
    for name in STATUS + [VALIDATED, DIMENSION]:
        gids = tags.get(name, [])
        if len(gids) > 1:
            print(f"note: {len(gids)} tags named {name!r}; using {gids[0]}")
        status_gid[name] = gids[0] if gids else ensure_tag(name)
    validated_gid = status_gid.pop(VALIDATED)
    kind_gid.update({"measure": MEASURE_TAG, "dimension": status_gid.pop(DIMENSION)})
    # every workspace tag with an old name, duplicates included; never created
    old_gid.update({gid: name for name in OLD_TAGS for gid in tags.get(name, [])})

    # ------------------------------------------------------------ dashboards
    top = get_all(
        f"/projects/{PROJECT}/tasks",
        {"opt_fields": "name,tags.name,memberships.section.name"},
    )
    dashboards = dashboard_gids(top)
    if ONLY and ONLY not in dashboards:
        sys.exit(f"--only {ONLY} is not a task tagged '{DASHBOARD_TAG}'.")
    # the dashboards this run covers: None means every dashboard
    scope = (
        {ONLY}
        if ONLY
        else set(dashboards_in_section(top, section_name))
        if section_name
        else None
    )
    if scope == set():
        sys.exit(f"--section {section_name!r} holds no task tagged '{DASHBOARD_TAG}'.")
    label = ONLY or section_name

    # ------------------------------------------------------------ 1. chain stages inside table tasks
    print("\n1. Stage chains")
    table_tasks = [t for t in top if TABLE.match(t["name"])]
    dim_rows = []  # table-task subtasks whose notes carry a `Used by:` line
    for t in table_tasks:
        subs = get_all(f"/tasks/{t['gid']}/subtasks", {"opt_fields": FIELDS})
        for x in subs:
            kind = next(
                (k for k in ("mart", "cube", "view") if x["name"].startswith(k + ":")),
                "addition",
            )
            stage_map[x["gid"]] = {
                "kind": kind,
                "completed": x["completed"],
                "name": x["name"],
            }
            used_by = USED_BY.search(x.get("notes") or "")
            if kind == "addition" and used_by:
                # the line holds Asana links to dashboards; a task link carries its gid
                x["used_by"] = set(re.findall(r"\b(\d{16})\b", used_by.group(1)))
                dim_rows.append(x)
        stage = {
            k: [x for x in subs if x["name"].startswith(k + ":")]
            for k in ("mart", "cube", "view")
        }
        for upstream, downstream in (("mart", "cube"), ("cube", "view")):
            for d in stage[downstream]:
                have = {x["gid"] for x in d.get("dependencies", [])}
                need = [u["gid"] for u in stage[upstream] if u["gid"] not in have]
                if need and scope is None:
                    write(
                        f"{t['name']}: '{upstream}' blocks '{d['name']}'",
                        "POST",
                        f"/tasks/{d['gid']}/addDependencies",
                        {"dependencies": need},
                    )

    # ------------------------------------------------------------ 2-6. measure and dimension rows
    print("\n2-6. Measure and dimension rows")
    # Gather every dashboard's rows before any write, so the --only guard below sees them all.
    plans = []  # (dashboard gid, [(row, kind, parent or None)])
    for dash in dashboards:
        if scope is not None and dash not in scope:
            continue
        children = get_all(
            f"/tasks/{dash}/subtasks", {"opt_fields": ROWF + ",num_subtasks"}
        )
        # rows under the dashboard's PR tasks
        grandchildren = {
            c["gid"]: get_all(f"/tasks/{c['gid']}/subtasks", {"opt_fields": ROWF})
            for c in children
            if c.get("num_subtasks") and not TABLE.match(c["name"])
        }
        nested, _ = rows_under({"gid": dash}, children, grandchildren)
        # an untagged row under a PR task is there by its `Used by:` line: a dimension
        plan = [
            (r, row_kind(r) or "dimension", parent)
            for r, parent in nested
            if parent is not None
        ]
        plan += [(r, kind, None) for r, kind in direct_rows(children)]
        plans.append((dash, plan))
    only_dim_rows = [r for r in dim_rows if scope is None or scope & r["used_by"]]
    # with no verdict for any row, --apply would strip the whole dashboard's 'validated' tags
    if scope is not None and APPLY and validation is not None:
        gids = {r["gid"] for _, plan in plans for r, _, _ in plan}
        gids |= {r["gid"] for r in only_dim_rows}
        if not gids & validation.keys():
            sys.exit(
                f"latest.json has no verdict for any row of {label}: merge this run's verdicts first."
            )

    for _, plan in plans:
        blockers_of = {}
        for r, kind, parent in plan:
            if parent is None:
                sync_row(r, kind)
                continue
            if parent["gid"] not in blockers_of:
                blockers_of[parent["gid"]] = get_all(
                    f"/tasks/{parent['gid']}/dependencies",
                    {"opt_fields": "name,completed"},
                )
            sync_row(r, kind, parent, blockers_of[parent["gid"]])

    for r in only_dim_rows:
        # a table-task row keeps its own kind tag; an untagged one is a dimension
        sync_row(r, row_kind(r) or "dimension")
    report_unknown_used_by = sorted(
        f"{r['name'][:60]} ({r['gid']}): {g}"
        for r in dim_rows
        for g in r["used_by"]
        if g not in dashboards
    )

    print(f"\n{'Applied' if APPLY else 'Would apply'} {len(changes)} change(s).")
    if report_ticked:
        print(f"\nTicked: live in Cube ({len(report_ticked)}):")
        print("\n".join("  " + x for x in report_ticked))
    if report_untick:
        print(
            f"\nUnticked: done rows that are not live in Cube ({len(report_untick)}):"
        )
        print("\n".join("  " + x for x in report_untick))
    if report_blocked_on_main:
        print(
            "\nMembers on main but a blocker is open (a cut's blocker belongs on its dimension row; close a shipped stage):"
        )
        print("\n".join("  " + x for x in report_blocked_on_main))
    if report_unknown_used_by:
        print(f"\n`Used by:` names a task that is not tagged '{DASHBOARD_TAG}':")
        print("\n".join("  " + x for x in report_unknown_used_by))
    if report_unverified:
        print("\nBlockers done but not verified on main (left open):")
        print("\n".join("  " + x for x in report_unverified))
    if report_gaps:
        print(
            f"\nLatest validation did not pass (give each gap a subtask under the row; see ~/asana-sync/validation/) ({len(report_gaps)}):"
        )
        print("\n".join("  " + x for x in report_gaps))
    if not APPLY:
        print("\nPreview only. Re-run with --apply to make these changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
