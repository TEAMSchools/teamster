"""Keep "Data Marts + Semantic Layer" in sync with its dependencies and with what ships in Cube.

  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid>          # preview, changes nothing
  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid> --apply  # make the changes

--only limits the run to one dashboard task's measure and dimension rows and skips step 1, so a validation
changes nothing else; without it the run covers every dashboard. Run it from a teamster checkout: it runs `git fetch` and reads
src/cube/model on origin/main.

Needs ASANA_PAT, your own personal access token, in the environment for both modes. Create one in Asana's
developer console (app.asana.com/0/my-apps), then load it without echoing it or saving it to history:
  read -rs ASANA_PAT && export ASANA_PAT

Rows are a dashboard task's measure subtasks (notes carry a `Status:` line) and its dimension rows: the subtasks of
table tasks, other than `mart:` / `cube:` / `view:` stages, that block the dashboard task. One dimension row lives
on the table its column comes from and blocks every dashboard that uses it. Each run:
  1. Chains stages inside every table task: `mart:` blocks `cube:`, `cube:` blocks `view:` (adds only missing links).
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
     in subtasks under the row, never in a tag.
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
APPLY = "--apply" in sys.argv
ONLY = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv[:-1] else None
MEASURE_TAG, DUP_MEASURE_TAG = "1214073246940451", "1215598455588323"
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
LATEST = os.path.expanduser("~/asana-sync/validation/latest.json")
# A missing file would read as "never validated" and strip every row's 'validated' tag.
if not os.path.exists(LATEST):
    sys.exit(f"No {LATEST}: merge the run's verdicts into it first.")
validation = json.load(open(LATEST))["rows"]
TABLE = re.compile(r"^(dim|fct|bridge)_[a-z0-9_]+$")
DASHBOARDS = """1213823831141286 1213823831345180 1213823922772842 1213823789013913 1213823922716082 1213823789082035
1213823789021563 1213823788919470 1213823788795999 1213823788719391 1213823922414217 1213823922758693 1213823831158360
1213823907731242 1213823925884528 1214609542482087 1214609542482089 1214609542482091 1214609542482093 1213823788976510
1213823922720520 1213823789000345 1213823922713816 1213823831344988 1219235026691519 1213823789062126 1213823925649913
1213823831350808 1213823789095486 1213823925620145""".split()
TABLE_UMBRELLAS = [
    "1219235117880911"
]  # NJ tier / 504 task: its subtasks are table tasks too
if ONLY and ONLY not in DASHBOARDS:
    sys.exit(f"--only {ONLY} is not a dashboard task in DASHBOARDS.")

token = (os.environ.get("ASANA_PAT") or "").strip() or sys.exit(
    "Set ASANA_PAT first: read -rs ASANA_PAT && export ASANA_PAT"
)
import requests  # noqa: E402

s = requests.Session()
s.headers.update({"Authorization": f"Bearer {token}"})
changes = []


def call(method, path, data=None, params=None):
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


# ---------------------------------------------------------------- shipped Cube members on main
def git(*args):
    # trunk-ignore(bandit/B603,bandit/B607): hardcoded git command, no user input
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, check=False
    ).stdout


git("fetch", "origin", "main", "-q")
views = git(
    "ls-tree", "-r", "--name-only", "origin/main", "src/cube/model/views"
).split()
shipped = set()
for v in views:
    if v.endswith(".yml"):
        y = git("show", f"origin/main:{v}")
        vname = os.path.basename(v)[:-4]
        for m in re.findall(r"^\s{10}-\s+([a-z0-9_]+)\s*$", y, re.M):
            shipped |= {m, f"{vname}.{m}"}
print(
    f"Cube members on public views (origin/main): {len([x for x in shipped if '.' in x])}"
)
# every measure / dimension name defined in any cube (public or not): a word only counts as a Cube member if it's here
cube_members = set()
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

# ---------------------------------------------------------------- tags by name
tags = {}
for t in get_all(f"/workspaces/{WORKSPACE}/tags", {"opt_fields": "name"}):
    tags.setdefault(t["name"], []).append(t["gid"])


def ensure_tag(name):
    """Create a missing tag on --apply; in preview, return a placeholder and say so."""
    if not APPLY:
        print(f"  would: create tag '{name}'")
        return f"new:{name}"
    # call() wraps the payload in {"data": ...} itself.
    return call("POST", "/tags", {"name": name, "workspace": WORKSPACE})["data"]["gid"]


status_gid = {}
for name in STATUS + [VALIDATED, DIMENSION]:
    gids = tags.get(name, [])
    if len(gids) > 1:
        print(f"note: {len(gids)} tags named {name!r}; using {gids[0]}")
    status_gid[name] = gids[0] if gids else ensure_tag(name)
validated_gid = status_gid.pop(VALIDATED)
kind_gid = {"measure": MEASURE_TAG, "dimension": status_gid.pop(DIMENSION)}
# every workspace tag with an old name, duplicates included; never created
old_gid = {gid: name for name in OLD_TAGS for gid in tags.get(name, [])}

# ---------------------------------------------------------------- 1. chain stages inside table tasks
print("\n1. Stage chains")
top = get_all(f"/projects/{PROJECT}/tasks", {"opt_fields": "name"})
table_tasks = [t for t in top if TABLE.match(t["name"])]
for u in TABLE_UMBRELLAS:
    table_tasks += [
        t
        for t in get_all(f"/tasks/{u}/subtasks", {"opt_fields": "name"})
        if TABLE.match(t["name"])
    ]
FIELDS = "name,completed,dependencies.gid,parent.name"
stage_map = {}  # gid of every table-task subtask -> its kind (mart / cube / view / addition) and state
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
    stage = {
        k: [x for x in subs if x["name"].startswith(k + ":")]
        for k in ("mart", "cube", "view")
    }
    for upstream, downstream in (("mart", "cube"), ("cube", "view")):
        for d in stage[downstream]:
            have = {x["gid"] for x in d.get("dependencies", [])}
            need = [u["gid"] for u in stage[upstream] if u["gid"] not in have]
            if need and not ONLY:
                write(
                    f"{t['name']}: '{upstream}' blocks '{d['name']}'",
                    "POST",
                    f"/tasks/{d['gid']}/addDependencies",
                    {"dependencies": need},
                )

# ---------------------------------------------------------------- 2-6. measure and dimension rows
print("\n2-6. Measure and dimension rows")
ROWF = "name,completed,notes,tags.name,tags.gid,dependencies"
# blockers are classified from stage_map (loaded in step 1): mart / cube / view stages, or "addition" for any other
# subtask of a table task (column work). Anything else a row depends on (e.g. a privacy review) isn't a status input.
NEEDS = re.compile(r"^\s*Needs:\s*(cube|data)\b", re.M | re.I)


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


report_ticked, report_untick, report_unverified = [], [], []
report_blocked_on_main, report_gaps = [], []


def sync_row(r, kind):
    """Steps 2-6 for one measure row or one dimension row."""
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
    # 5. validation results from the cube-dashboard skill
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
    if live:
        want = None
    elif any(b["kind"] in ("mart", "addition") for b in open_blockers):
        want = "needs-data"
    elif open_blockers:
        want = "needs-cube"
    elif needs:
        want = f"needs-{needs.group(1).lower()}"
    else:
        want = None
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


report_odd_dash_blockers = []
dims_done = set()  # a dimension row blocks every dashboard that uses it; sync it once
for dash in DASHBOARDS:
    if ONLY and dash != ONLY:
        continue
    rows = get_all(f"/tasks/{dash}/subtasks", {"opt_fields": ROWF})
    # with no verdict for any row, --apply would strip the whole dashboard's 'validated' tags
    if ONLY and APPLY and not any(r["gid"] in validation for r in rows):
        sys.exit(
            f"latest.json has no verdict for any row of {ONLY}: merge this run's verdicts first."
        )
    for r in rows:
        if "Status:" in (r.get("notes") or ""):
            sync_row(r, "measure")
        # anything else (checklist steps etc.) is not a row
    for d in get_all(f"/tasks/{dash}/dependencies", {"opt_fields": "name"}):
        st = stage_map.get(d["gid"])
        if not st or st["kind"] != "addition":
            # a dashboard blocks only on dimension rows; a stage or outside task there is a misplaced link
            report_odd_dash_blockers.append(f"{dash}: {d.get('name', d['gid'])[:70]}")
        elif d["gid"] not in dims_done:
            dims_done.add(d["gid"])
            sync_row(
                call("GET", f"/tasks/{d['gid']}", params={"opt_fields": ROWF})["data"],
                "dimension",
            )

print(f"\n{'Applied' if APPLY else 'Would apply'} {len(changes)} change(s).")
if report_ticked:
    print(f"\nTicked: live in Cube ({len(report_ticked)}):")
    print("\n".join("  " + x for x in report_ticked))
if report_untick:
    print(f"\nUnticked: done rows that are not live in Cube ({len(report_untick)}):")
    print("\n".join("  " + x for x in report_untick))
if report_blocked_on_main:
    print(
        "\nMembers on main but a blocker is open (a cut's blocker belongs on its dimension row; close a shipped stage):"
    )
    print("\n".join("  " + x for x in report_blocked_on_main))
if report_odd_dash_blockers:
    print(
        "\nDashboard blockers that are not dimension rows (link the dimension row on the table task instead):"
    )
    print("\n".join("  " + x for x in report_odd_dash_blockers))
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
