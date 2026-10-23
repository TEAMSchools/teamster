"""Keep "Data Marts + Semantic Layer" in sync with its dependencies and with what ships in Cube.

  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid>          # preview, changes nothing
  uv run --with requests python scripts/asana_sync.py --only <dashboard task gid> --apply  # make the changes

--only limits the run to one dashboard task's measure rows and skips step 1, so a validation changes nothing
else; without it the run covers every dashboard. Run it from a teamster checkout: it runs `git fetch` and reads
src/cube/model on origin/main.

Needs ASANA_PAT, your own personal access token, in the environment for both modes. Create one in Asana's
developer console (app.asana.com/0/my-apps), then load it without echoing it or saving it to history:
  read -rs ASANA_PAT && export ASANA_PAT

Each run:
  1. Chains stages inside every table task: `mart:` blocks `cube:`, `cube:` blocks `view:` (adds only missing links).
  2. Recomputes each measure row's status tag from evidence only, never from a tag already on the row
     (is it in Cube? whether it matches is step 5's tag):
       the latest validation found a missing Cube member                      -> cube-partial
       every member its notes name is on a public view on main, no open blocker -> cube-covered
       otherwise an open mart stage or column addition                        -> mart-missing
       otherwise an open cube / view stage                                    -> mart-ready
       otherwise (no evidence either way)                                     -> untriaged
  3. Ticks a row only when it is cube-covered AND tagged 'matched'. Every other done row is unticked, with the
     reason in the report.
  4. Keeps the project's own `measure` tag on rows (drops the duplicate workspace tag of the same name).
  5. Reads ~/asana-sync/validation/latest.json (the cube-dashboard skill's latest verdict per row) and gives every row
     exactly one validation tag, removing the others:
       pass                           -> 'matched'
       fail, missing_member, fix_cube, fix_source, undecided -> 'mismatch' (Cube's numbers differ; the digest says whether a missing
                                         member explains the gap)
       incomplete, or never validated -> 'unvalidated'
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
# Every row gets exactly one, from evidence only; untriaged = no evidence either way.
STATUS = ["cube-covered", "cube-partial", "mart-ready", "mart-missing", "untriaged"]
MISMATCH = "mismatch"
MATCHED = (
    "matched"  # the latest validation found Cube equal to the dashboard at every grain
)
UNVALIDATED = (
    "unvalidated"  # no run yet, or the latest run could not compare (incomplete)
)
# The one validation tag each latest verdict gives a row; any other verdict is unvalidated.
VALIDATION_TAG = {
    "pass": MATCHED,
    "fail": MISMATCH,
    "missing_member": MISMATCH,
    "fix_cube": MISMATCH,
    "fix_source": MISMATCH,
    "undecided": MISMATCH,
}
LATEST = os.path.expanduser("~/asana-sync/validation/latest.json")
# A missing file would read as "never validated" and strip every row's validation tag.
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
for name in STATUS:
    gids = tags.get(name, [])
    if len(gids) > 1:
        print(f"note: {len(gids)} tags named {name!r}; using {gids[0]}")
    status_gid[name] = gids[0] if gids else ensure_tag(name)
validation_gid = {}
for tag_name in (MATCHED, MISMATCH, UNVALIDATED):
    gids = tags.get(tag_name, [])
    validation_gid[tag_name] = gids[0] if gids else ensure_tag(tag_name)

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

# ---------------------------------------------------------------- 2-4. measure rows
print("\n2-4. Measure rows")
ROWF = "name,completed,notes,tags.name,tags.gid,dependencies"
# blockers are classified from stage_map (loaded in step 1): mart / cube / view stages, or "addition" for any other
# subtask of a table task (column work). Anything else a row depends on (e.g. a privacy review) isn't a status input.


def members_named(notes):
    m = re.search(
        r"Where it lives:\s*(.*?)(?:\n\s*Regions:|\n\s*Was:|\n\s*https?://|$)",
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


report_untick, report_unverified, report_mismatch, report_partial, report_ticked = (
    [],
    [],
    [],
    [],
    [],
)
for dash in DASHBOARDS:
    if ONLY and dash != ONLY:
        continue
    rows = get_all(f"/tasks/{dash}/subtasks", {"opt_fields": ROWF})
    # with no verdict for any row, --apply would mark the whole dashboard unvalidated
    if ONLY and APPLY and not any(r["gid"] in validation for r in rows):
        sys.exit(
            f"latest.json has no verdict for any row of {ONLY}: merge this run's verdicts first."
        )
    for r in rows:
        if "Status:" not in (r.get("notes") or ""):
            continue  # checklist items etc.
        rid, name = r["gid"], r["name"][:70]
        have = {t["gid"] for t in r.get("tags", [])}
        if DUP_MEASURE_TAG in have:
            write(
                f"{name}: duplicate 'measure' tag -> project 'measure' tag",
                "POST",
                f"/tasks/{rid}/removeTag",
                {"tag": DUP_MEASURE_TAG},
            )
        if MEASURE_TAG not in have:
            write(
                f"{name}: add 'measure' tag",
                "POST",
                f"/tasks/{rid}/addTag",
                {"tag": MEASURE_TAG},
            )
        deps = r.get("dependencies")
        if deps is None:
            deps = get_all(f"/tasks/{rid}/dependencies", {"opt_fields": "name"})
        blockers = [
            (stage_map[d["gid"]]["kind"], stage_map[d["gid"]])
            for d in deps
            if d["gid"] in stage_map
        ]
        done = r["completed"]
        named = members_named(r.get("notes"))
        cube_named = {
            x for x in named if member(x) in cube_members
        }  # only real Cube measure/dimension names
        verified = bool(cube_named) and all(member(x) in shipped for x in cube_named)
        # 5. validation results from the cube-dashboard skill
        v = validation.get(rid, {})
        verdict = v.get("verdict")
        reopen = v.get("reopen_for", [])
        failed = verdict == "fail"
        # a member Cube lacks causes part of the gap (whatever else is wrong): the row is not shipped
        partial = verdict == "missing_member" or bool(reopen)
        matched = verdict == "pass"
        # Exactly one validation tag, from the latest verdict: never inferred from a blank.
        want_v = VALIDATION_TAG.get(verdict, UNVALIDATED)
        for tag_name, gid in validation_gid.items():
            if tag_name == want_v and gid not in have:
                write(
                    f"{name}: latest validation {verdict or 'never run'} -> add '{tag_name}'",
                    "POST",
                    f"/tasks/{rid}/addTag",
                    {"tag": gid},
                )
            elif tag_name != want_v and gid in have:
                write(
                    f"{name}: latest validation {verdict or 'never run'} -> remove '{tag_name}'",
                    "POST",
                    f"/tasks/{rid}/removeTag",
                    {"tag": gid},
                )
        mismatched = want_v == MISMATCH
        if partial:
            report_partial.append(
                f"{name} ({rid}): add to Cube: {', '.join(reopen) or 'see the digest'}"
            )
        if mismatched:
            report_mismatch.append(f"{name} ({rid}): Cube does not match Tableau")
        # 2. status tag: does the row ship in Cube today?
        blockers_done = all(d.get("completed") for _, d in blockers)
        # Status comes from evidence only, never from a tag already on the row: the stage
        # blockers, the members its notes name being on main, and the latest validation.
        # The status tag says whether the row is in Cube; whether its numbers match is the
        # validation tag's job. A failing row that ships stays cube-covered (and open).
        covered = verified and blockers_done and not partial
        if partial:
            want = "cube-partial"
        elif covered:
            want = "cube-covered"
        elif any(
            k in ("mart", "addition") and not d.get("completed") for k, d in blockers
        ):
            want = "mart-missing"
        elif any(k in ("cube", "view") and not d.get("completed") for k, d in blockers):
            want = "mart-ready"
        else:
            want = "untriaged"  # no evidence either way: nobody has worked out what it needs
        # 3. done means it ships in Cube and its numbers matched the dashboard
        if covered and matched and not done:
            write(
                f"{name}: cube-covered and matched -> tick done",
                "PUT",
                f"/tasks/{rid}",
                {"completed": True},
            )
            report_ticked.append(f"{name} ({rid})")
        elif done and not (covered and matched):
            why = []
            if not verified:
                gone = sorted(x for x in cube_named if member(x) not in shipped)
                why.append(
                    f"not on main: {', '.join(gone)}"
                    if gone
                    else "its notes name no member Cube defines on main"
                )
            if not blockers_done:
                why.append("a blocker is open")
            if failed:
                why.append("validation failed")
            if partial:
                why.append("Cube lacks a member")
            if verdict == "fix_cube":
                why.append("Cube's formula differs from the dashboard")
            if verdict == "fix_source":
                why.append("the source data is wrong")
            if verdict == "undecided":
                why.append("the domain owner has not decided who fixes a mismatch")
            if (
                not matched
                and not failed
                and not partial
                and verdict not in ("fix_cube", "fix_source", "undecided")
            ):
                why.append(f"not validated ({verdict or 'never run'})")
            write(
                f"{name}: {'; '.join(why)} -> untick",
                "PUT",
                f"/tasks/{rid}",
                {"completed": False},
            )
            report_untick.append(f"{name} ({rid}): {'; '.join(why)}")
        if not done and blockers and blockers_done and not verified:
            report_unverified.append(
                f"{name} ({rid}): blockers done, but Cube member(s) not found on main: {', '.join(sorted(cube_named)) or 'none named'}"
            )
        current = [n for n in STATUS if status_gid[n] in have]
        if want and current != [want]:
            for n in current:
                if n != want:
                    write(
                        f"{name}: remove '{n}'",
                        "POST",
                        f"/tasks/{rid}/removeTag",
                        {"tag": status_gid[n]},
                    )
            if want not in current:
                write(
                    f"{name}: add '{want}'",
                    "POST",
                    f"/tasks/{rid}/addTag",
                    {"tag": status_gid[want]},
                )

print(f"\n{'Applied' if APPLY else 'Would apply'} {len(changes)} change(s).")
if report_ticked:
    print(f"\nTicked: cube-covered and matched ({len(report_ticked)}):")
    print("\n".join("  " + x for x in report_ticked))
if report_untick:
    print(
        f"\nUnticked: done rows that are not both cube-covered and matched ({len(report_untick)}):"
    )
    print("\n".join("  " + x for x in report_untick))
if report_unverified:
    print("\nBlockers done but not verified on main (left open):")
    print("\n".join("  " + x for x in report_unverified))
if report_mismatch:
    print(f"\nRows tagged '{MISMATCH}' (see ~/asana-sync/validation/):")
    print("\n".join("  " + x for x in report_mismatch))
if report_partial:
    print("\nRows tagged cube-partial: Cube lacks a member the dashboard uses:")
    print("\n".join("  " + x for x in report_partial))
if not APPLY:
    print("\nPreview only. Re-run with --apply to make these changes.")
