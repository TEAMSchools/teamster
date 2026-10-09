# Truth issues and a measured settle window: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A validation gap the dashboard causes gets a `truth_issue` verdict, a
`needs-review` tag and a drafted GitHub issue for the domain owner; and a
`settle` command measures how many days before an extract refresh scores still
change.

**Architecture:** Everything lands in `scripts/cube_validate.py`. A metric's
`variants:` (corrected SQL, each naming what it `explains`) generalize the
existing `sql_without`. Truth issues and their rulings live in the checks file;
the script reads them and never calls GitHub or Asana. The skill does the filing
and reads the owner's labels. `~/asana-sync/sync.py` (outside the repo) maps the
new verdict to a tag.

**Tech Stack:** Python 3.13, PyYAML, pytest, `tableauhyperapi` (run time only),
`google-cloud-bigquery` (ADC).

**Spec:** `docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`,
revisions "truth issues go to the domain owner" and "measure each dashboard's
settle window".

## Global Constraints

- Always `uv run`. The suite is
  `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5` (161
  tests pass at the start).
- No student names or ids in any output, draft, comment, commit or chat. Cells
  under 10 students show as "small cell".
- The script never calls GitHub or Asana.
- Stage files by name. Never stage
  `.claude/skills/cube-dashboard/checks/state_testing_analysis_tool.yml` or
  `.devcontainer/tpl/.env.tpl` (both carry unrelated uncommitted changes).
- Open files under `.claude/` with the Read tool, never `cat`.
- Before pushing markdown or YAML, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. If a
  hook blocks `-m`, write the message to the session scratchpad and use `-F`.
- `~/asana-sync/sync.py` is outside the repo: back it up before editing; the
  user runs it.
- Resolved "to confirm" items from the spec: the labels `validation`,
  `cube-correct` and `cube-wrong` do not exist yet (Task 7 creates them);
  `sync.py`'s `ensure_tag` creates `needs-review` itself; the GitHub MCP has no
  label-event read, so `ruling.by` is the issue's assignee.

## Review Focus

- Test-record ids from `workbook_excludes` must never reach a drafted issue's
  SQL. Task 4 tests it.
- A per-student grain's explained examples must show "a student", never the id.
  Task 2 tests it.
- A filed truth issue (`issue:` set) must never get a second draft. Task 4 tests
  it.
- A closed truth issue that explains no cell is reported stale; an open one that
  explains none is silent. Task 3 tests it.
- Settle: rows with no date, and rows dated after the refresh, must not drive
  the recommendation. Task 5 tests it.

---

### Task 1: Variants replace the single without-SQL

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks` ~L1026-1037 and the
  `definition` tuple ~L1088; `truth_sql` ~L1272-1278; `Cell` ~L1333; `explain`
  ~L1390; `summarize` ~L1397; `run_dashboard` ~L1998-2002 and ~L2082-2085)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: every loaded metric has `m["variants"]`, a list of dicts with
  `explains: list[str]` and `sql` (count) or `num`/`den` (rate, average). A
  metric with `missing_members` and `sql_without`/`num_without`/`den_without`
  gets that as variant 0. Truth-SQL aliases: `m{i}_v{j}` (count) or
  `m{i}_v{j}_num`/`m{i}_v{j}_den`.
- Produces: `Cell.explained_by: tuple[str, ...]`, `Cell.variant: float | None`,
  `Cell.explained` (a property, `bool(explained_by)`).
- Produces: `explain(cells, kind, variants)` where `variants` is a list of
  `(names, truth_cells_dict)`; `summarize(cells, kind, variants=())` adds
  `explained_by: dict[str, int]` to its output.

- [ ] **Step 1: Write the failing tests**

Append to `tests/scripts/test_cube_validate.py`:

```python
# ---------------------------------------------------------------- variants
def test_load_checks_turns_sql_without_into_variant_zero(tmp_path):
    c = cv.load_checks(_write_variant(tmp_path, _add_missing_member))
    assert c["rows"][0]["metrics"][0]["variants"] == [
        {"explains": ["team"], "sql": "countif(att_code = 'T')"}
    ]
    assert c["rows"][1]["metrics"][0]["variants"] == []


def test_load_checks_variant_needs_explains_and_its_sql(tmp_path):
    def m(d):
        d["rows"][0]["metrics"][0]["variants"] = [{"sql": "count(1)"}]

    with pytest.raises(cv.CheckError, match="each variant needs"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_explain_takes_the_first_variant_that_matches():
    cells = cv.compare("count", {("B",): 15.0}, {("B",): (12.0, 120)})
    cv.explain(
        cells,
        "count",
        [(["a"], {("B",): (14.0, 120)}), (["b"], {("B",): (15.0, 120)}),
         (["c"], {("B",): (15.0, 120)})],
    )
    assert cells[0].explained_by == ("b",)
    assert cells[0].variant == 15.0


def test_summarize_counts_explained_cells_by_cause():
    cells = cv.compare(
        "count", {("B",): 15.0, ("C",): 5.0}, {("B",): (12.0, 120), ("C",): (8.0, 80)}
    )
    cv.explain(cells, "count", [(["team"], {("B",): (15.0, 120), ("C",): (5.0, 80)})])
    s = cv.summarize(cells, "count")
    assert s["explained"] == 2 and s["explained_by"] == {"team": 2}
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "variant or explain_takes or by_cause" 2>&1 | tail -n 8`
Expected: 4 failures (`KeyError: 'variants'`, no "each variant needs" error,
`explain` treating its list as a dict, no `explained_by` key).

- [ ] **Step 3: Implement**

In `load_checks`, replace the `if m.get("missing_members"):` block (the one
raising "lists missing_members, so it needs") with:

```python
            if m.get("missing_members") and not m.get("variants"):
                need = (
                    ("sql_without",)
                    if m["kind"] == "count"
                    else ("num_without", "den_without")
                )
                missing = [k for k in need if not m.get(k)]
                if missing:
                    raise CheckError(
                        f"{where}: metric {m.get('cube')} lists missing_members, so "
                        f"it needs {missing}: the same SQL without the missing field"
                    )
            variants = list(m.get("variants") or [])
            if m.get("missing_members") and m.get("sql_without" if m["kind"] == "count" else "num_without"):
                # The SQL without the missing members is the variant that explains them.
                keys = ("sql",) if m["kind"] == "count" else ("num", "den")
                variants.insert(
                    0,
                    {
                        "explains": list(m["missing_members"]),
                        **{k: m[f"{k}_without"] for k in keys},
                    },
                )
            need = ("explains", "sql") if m["kind"] == "count" else ("explains", "num", "den")
            for v in variants:
                if not isinstance(v, dict) or any(not v.get(k) for k in need):
                    raise CheckError(
                        f"{where}: metric {m.get('cube')}: each variant needs "
                        f"{list(need)}"
                    )
            m["variants"] = variants
```

Add `"variants"` to the `definition` tuple.

In `truth_sql`, replace the two `missing_members` branches (the `_alt` selects)
with:

```python
        for j, v in enumerate(m.get("variants", [])):
            if m["kind"] == "count":
                select.append(f"{v['sql']} as m{i}_v{j}")
            else:
                select += [
                    f"{v['num']} as m{i}_v{j}_num",
                    f"{v['den']} as m{i}_v{j}_den",
                ]
```

Replace `Cell`'s `explained` field and add the property:

```python
@dataclass
class Cell:
    key: tuple[str, ...]
    cube: float | None
    truth: float | None
    n_students: int | None
    ok: bool
    # Fails as written, but matches a variant: the names that variant explains.
    explained_by: tuple[str, ...] = ()
    variant: float | None = None  # that variant's value

    @property
    def explained(self) -> bool:
        return bool(self.explained_by)

    @property
    def delta(self) -> float:
        if self.cube is None or self.truth is None:
            return float("inf")
        return abs(self.cube - self.truth)
```

Replace `explain` and `summarize`:

```python
def explain(cells, kind, variants) -> None:
    """Mark failed cells that match a variant; the first that matches names the cause."""
    for c in cells:
        if c.ok:
            continue
        for names, alt in variants:
            v = alt.get(c.key, (None, None))[0]
            if _matches(kind, c.cube, v):
                c.explained_by, c.variant = tuple(names), v
                break


def _cell_out(c, kind) -> dict:
    return {
        "key": list(c.key),
        "cube": c.cube,
        "truth": c.truth,
        "n_students": c.n_students,
        "kind": kind,
    }


def summarize(cells, kind, variants=()) -> dict:
    bad = sorted(
        (c for c in cells if not c.ok and not c.explained), key=lambda c: -c.delta
    )
    by: dict[str, int] = {}
    for c in cells:
        for n in c.explained_by:
            by[n] = by.get(n, 0) + 1
    only = None
    if len(cells) == 1:
        only = {"cube": cells[0].cube, "truth": cells[0].truth}
        if variants:
            # Variant 0 is the SQL without the missing members, when there are any.
            only["without"] = variants[0][1].get(cells[0].key, (None, None))[0]
    return {
        "cells": len(cells),
        "bad": len(bad),
        "explained": sum(1 for c in cells if c.explained),
        "explained_by": by,
        "only": only,
        "worst": [_cell_out(c, kind) for c in bad[:5]],
    }
```

In `run_dashboard`'s `compare_job`, replace the `alt = None ... summaries[...]`
lines with:

```python
                variants = [
                    (v["explains"], truth_cells(trows, len(g), i, m["kind"], f"_v{j}"))
                    for j, v in enumerate(m["variants"])
                ]
                explain(cells, m["kind"], variants)
                summaries[m["key"]] = summarize(cells, m["kind"], variants)
```

In the row loop, replace `mm["explains_cells"] += ms[m["key"]]["explained"]`
with `mm["explains_cells"] += ms[m["key"]]["explained_by"].get(name, 0)`.

In `_diagnose`, a metric can now list missing members with only `variants:` and
no without-SQL. Change `if metric.get("missing_members"):` to:

```python
    without = "sql_without" if metric["kind"] == "count" else "num_without"
    if metric.get("missing_members") and metric.get(without):
```

- [ ] **Step 4: Move the old tests to the new aliases**

Run: `sed -i 's/m0_alt/m0_v0/g' tests/scripts/test_cube_validate.py`. Then edit
`test_explain_marks_cells_the_without_variant_matches`: change the `explain`
call's last argument to
`[(["team"], {("B",): (15.0, 120), ("C",): (6.0, 80)})]`. Check
`rg -n 'cv.Cell\(' tests/scripts/test_cube_validate.py` finds no `explained=`
keyword; fix any to `explained_by=("team",)`.

- [ ] **Step 5: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 165 passed.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a metric's variants name what each corrected SQL explains

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 2: Truth issues, rulings and the `truth_issue` verdict

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks`; constants near `KINDS`;
  `summarize`; `row_verdict`; `run_dashboard`; `_COMPARED`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 1's `variants`, `explain`, `summarize`, `Cell`.
- Produces: `checks["truth_issues"]: dict[str, dict]` (each with `title`,
  `what`, `where`, `labels: list`, optional `issue: int`,
  `ruling: {call, by, on, note}`, `closed_on`, `evidence`);
  `checks["open_issues_task"]: str | None`.
- Produces: `issue_states(checks) -> tuple[frozenset, frozenset, frozenset]`
  (accepted, rejected, open slugs).
- Produces:
  `summarize(cells, kind, variants=(), accepted=frozenset(), open_issues=frozenset())`,
  adding `review`, `accepted` and `examples` (up to 3 explained cells: the
  `_cell_out` fields plus `variant` and `explains`).
- Produces: grain entries carry `review` and `accepted`; grain status and row
  verdict can be `truth_issue`; each result row may carry
  `truth_issues: {slug: {explains_cells, issue, ruling, stale}}`.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------- truth issues
def _add_truth_issue(d, **extra):
    d["truth_issues"] = {
        "tardy_formula": {
            "title": "fix(tableau): the demo dashboard counts half days as tardy",
            "what": "The dashboard's tardy count includes half days.",
            "where": "dashboard",
            **extra,
        }
    }
    d["rows"][0]["metrics"][0]["variants"] = [
        {"explains": ["tardy_formula"], "sql": "countif(att_code = 'T')"}
    ]


def _truth_run(tmp_path, mutate=_add_truth_issue):
    checks = cv.load_checks(_write_variant(tmp_path, mutate))
    return checks, cv.run_dashboard(checks, FakeCube(), AltBQ(), TODAY, snapshots=SNAPS)


def test_load_checks_truth_issue_needs_title_what_where(tmp_path):
    def m(d):
        _add_truth_issue(d)
        del d["truth_issues"]["tardy_formula"]["where"]

    with pytest.raises(cv.CheckError, match="missing \\['where'\\]"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_load_checks_ruling_call_must_be_cube_correct_or_wrong(tmp_path):
    def m(d):
        _add_truth_issue(d, ruling={"call": "maybe", "by": "x", "on": "2026-10-09"})

    with pytest.raises(cv.CheckError, match="cube-correct or cube-wrong"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_load_checks_variant_must_explain_known_names(tmp_path):
    def m(d):
        _add_truth_issue(d)
        d["rows"][0]["metrics"][0]["variants"][0]["explains"] = ["nobody"]

    with pytest.raises(cv.CheckError, match="explains unknown \\['nobody'\\]"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_unruled_truth_issue_makes_the_row_truth_issue(tmp_path):
    _, result = _truth_run(tmp_path)
    row = result["rows"]["1"]
    assert row["verdict"] == "truth_issue"
    school = next(g for g in row["grains"] if g["grain"] == ["region", "school"])
    assert school["status"] == "truth_issue" and school["review"] == 2
    assert row["truth_issues"] == {
        "tardy_formula": {"explains_cells": 2, "issue": None, "ruling": None, "stale": False}
    }


def test_cube_correct_ruling_counts_the_cells_as_matches(tmp_path):
    ruling = {"call": "cube-correct", "by": "owner", "on": "2026-10-09"}
    _, result = _truth_run(tmp_path, lambda d: _add_truth_issue(d, ruling=ruling))
    row = result["rows"]["1"]
    assert row["verdict"] == "pass"
    assert row["truth_issues"]["tardy_formula"]["ruling"] == "cube-correct"


def test_cube_wrong_ruling_leaves_the_cells_unexplained(tmp_path):
    ruling = {"call": "cube-wrong", "by": "owner", "on": "2026-10-09"}
    _, result = _truth_run(tmp_path, lambda d: _add_truth_issue(d, ruling=ruling))
    assert result["rows"]["1"]["verdict"] == "fail"


def test_a_variant_can_explain_a_member_and_a_truth_issue_together(tmp_path):
    def m(d):
        _add_truth_issue(d)
        mm = d["rows"][0]["metrics"][0]
        mm["missing_members"] = ["team"]
        mm["variants"][0]["explains"] = ["tardy_formula", "team"]

    _, result = _truth_run(tmp_path, m)
    row = result["rows"]["1"]
    assert row["verdict"] == "truth_issue"
    assert row["missing_members"]["team"]["explains_cells"] == 2
    assert row["truth_issues"]["tardy_formula"]["explains_cells"] == 2


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (["truth_issue", "missing_member"], "truth_issue"),
        (["truth_issue", "fail"], "fail"),
        (["truth_issue", "error"], "incomplete"),
        (["pass", "truth_issue"], "truth_issue"),
    ],
)
def test_row_verdict_truth_issue(statuses, verdict):
    assert cv.row_verdict([{"status": s} for s in statuses]) == verdict


def test_unaccounted_construct_overrides_truth_issue(tmp_path):
    checks, _ = _truth_run(tmp_path)
    audit = {"1": {"unaccounted": [{"ref": "group: X [abc123]"}]}}
    result = cv.run_dashboard(checks, FakeCube(), AltBQ(), TODAY, audit=audit)
    assert result["rows"]["1"]["verdict"] == "incomplete"


def test_explained_examples_never_name_a_student(tmp_path):
    def m(d):
        _add_truth_issue(d)
        d["dimensions"]["school"]["person"] = True

    _, result = _truth_run(tmp_path, m)
    grain = next(
        g for g in result["rows"]["1"]["grains"] if g["grain"] == ["region", "school"]
    )
    examples = [c for s in grain["metrics"].values() for c in s["examples"]]
    assert examples and all(c["key"][1] == "a student" for c in examples)
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "truth or ruling or known_names or a_member_and" 2>&1 | tail -n 8`
Expected: failures on the missing validation messages, on verdicts reading
`missing_member`/`fail` instead of `truth_issue`, and on missing
`truth_issues`/`review`/`examples` keys.

- [ ] **Step 3: Implement**

Next to `KINDS`, add:

```python
# Where a truth issue lives, and the two answers a domain owner can give.
TRUTH_WHERE = ("dashboard", "rpt", "source")
RULINGS = ("cube-correct", "cube-wrong")
```

In `load_checks`, right after the `hard_filters` loop and before
`for row in data["rows"]:`, add:

```python
    # Gaps the dashboard, its rpt_ model or the source causes, for the domain owner.
    issues = data.get("truth_issues") or {}
    if not isinstance(issues, dict):
        raise CheckError(f"{path}: truth_issues is a map of slug to entry")
    for slug, t in issues.items():
        at = f"{path}: truth issue '{slug}'"
        missing = [k for k in ("title", "what", "where") if not (t or {}).get(k)]
        if missing:
            raise CheckError(f"{at} is missing {missing}")
        if t["where"] not in TRUTH_WHERE:
            raise CheckError(f"{at}: where must be one of {', '.join(TRUTH_WHERE)}")
        if t.get("issue") is not None and not isinstance(t["issue"], int):
            raise CheckError(f"{at}: issue is the GitHub issue number")
        r = t.get("ruling")
        if r is not None and not (
            isinstance(r, dict) and r.get("call") in RULINGS and r.get("by") and r.get("on")
        ):
            raise CheckError(
                f"{at}: ruling needs call (cube-correct or cube-wrong), by and on"
            )
        t["labels"] = list(t.get("labels") or [])
    data["truth_issues"] = issues
    data["open_issues_task"] = (
        str(data["open_issues_task"]) if data.get("open_issues_task") else None
    )
```

In the variant loop from Task 1 (inside `for v in variants:`), after the `need`
check, add:

```python
                known = set(issues) | set(m.get("missing_members") or [])
                unknown = [n for n in v["explains"] if n not in known]
                if unknown:
                    raise CheckError(
                        f"{where}: metric {m.get('cube')}: a variant explains unknown "
                        f"{unknown}; name a missing member or a truth issue"
                    )
```

Add after `row_verdict`'s definition site (top level):

```python
def issue_states(checks) -> tuple[frozenset, frozenset, frozenset]:
    """Truth issues the owner ruled cube-correct, ruled cube-wrong, and not yet ruled."""
    calls = {
        s: (t.get("ruling") or {}).get("call")
        for s, t in (checks.get("truth_issues") or {}).items()
    }
    return (
        frozenset(s for s, c in calls.items() if c == "cube-correct"),
        frozenset(s for s, c in calls.items() if c == "cube-wrong"),
        frozenset(s for s, c in calls.items() if c is None),
    )
```

Replace `summarize` (Task 1 version) with:

```python
def summarize(
    cells, kind, variants=(), accepted=frozenset(), open_issues=frozenset()
) -> dict:
    """One metric at one grain.

    A cell explained only by truth issues ruled cube-correct is accepted: the
    dashboard is wrong there and Cube is right, so it counts as a match.
    """

    def is_accepted(c):
        return c.explained and set(c.explained_by) <= accepted

    bad = sorted(
        (c for c in cells if not c.ok and not c.explained), key=lambda c: -c.delta
    )
    explained = [c for c in cells if c.explained and not is_accepted(c)]
    by: dict[str, int] = {}
    for c in cells:
        for n in c.explained_by:
            by[n] = by.get(n, 0) + 1
    only = None
    if len(cells) == 1:
        only = {"cube": cells[0].cube, "truth": cells[0].truth}
        if variants:
            # Variant 0 is the SQL without the missing members, when there are any.
            only["without"] = variants[0][1].get(cells[0].key, (None, None))[0]
    shown = sorted((c for c in cells if c.explained), key=lambda c: -c.delta)
    return {
        "cells": len(cells),
        "bad": len(bad),
        "explained": len(explained),
        "review": sum(1 for c in explained if set(c.explained_by) & open_issues),
        "accepted": sum(1 for c in cells if is_accepted(c)),
        "explained_by": by,
        "only": only,
        "worst": [_cell_out(c, kind) for c in bad[:5]],
        "examples": [
            dict(_cell_out(c, kind), variant=c.variant, explains=list(c.explained_by))
            for c in shown[:3]
        ],
    }
```

Replace `row_verdict`:

```python
def row_verdict(grains) -> str:
    statuses = [g["status"] for g in grains]
    if "fail" in statuses:
        return "fail"
    if "error" in statuses:
        return "incomplete"
    for s in ("truth_issue", "missing_member"):
        if s in statuses:
            return s
    if "pass" not in statuses:
        return "incomplete"
    return "pass"
```

In `run_dashboard`, before `def run_job`, add
`accepted, rejected, open_issues = issue_states(checks)`. In `compare_job`,
replace the Task 1 variant block with:

```python
                # A variant the owner ruled cube-wrong explains nothing.
                variants = [
                    (v["explains"], truth_cells(trows, len(g), i, m["kind"], f"_v{j}"))
                    for j, v in enumerate(m["variants"])
                    if not set(v["explains"]) & rejected
                ]
                explain(cells, m["kind"], variants)
                summaries[m["key"]] = summarize(
                    cells, m["kind"], variants, accepted, open_issues
                )
```

and change the person loop's inner `for c in s_["worst"]:` to
`for c in [*s_["worst"], *s_["examples"]]:`.

In the row loop, replace the `entry.update(status=... "pass"), ...)` call with:

```python
                review = sum(s["review"] for s in ms.values())
                entry.update(
                    status="fail"
                    if bad
                    else "truth_issue"
                    if review
                    else ("missing_member" if explained else "pass"),
                    cells=sum(s["cells"] for s in ms.values()),
                    bad=bad,
                    explained=explained,
                    review=review,
                    accepted=sum(s["accepted"] for s in ms.values()),
                    metrics=ms,
                    pre_aggregations=o["pre_aggregations"],
                )
```

Change the audit tuple `("pass", "missing_member")` to
`("pass", "missing_member", "truth_issue")`. Before
`result["rows"][str(row["row_gid"])] = {`, add:

```python
        truth = {}
        named = {
            n
            for m in row["metrics"]
            for v in m["variants"]
            for n in v["explains"]
            if n in checks["truth_issues"]
        }
        for slug in sorted(named):
            t = checks["truth_issues"][slug]
            n = sum(
                s["explained_by"].get(slug, 0)
                for g in grains
                for s in g.get("metrics", {}).values()
            )
            truth[slug] = {
                "explains_cells": n,
                "issue": t.get("issue"),
                "ruling": (t.get("ruling") or {}).get("call"),
                # A closed issue that explains nothing any more: remove its entry.
                "stale": bool(t.get("closed_on")) and not n,
            }
```

and add `**({"truth_issues": truth} if truth else {}),` to the row dict. Set
`_COMPARED = ("pass", "fail", "missing_member", "truth_issue")`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 178 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a truth_issue verdict for gaps the dashboard causes

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 3: Truth issues in the comment, digest, report and latest.json

**Files:**

- Modify: `scripts/cube_validate.py` (`comment_text`, `digest_markdown`,
  `report_markdown`, `write_outputs`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 2's row `truth_issues` and grain `review`.
- Produces: `latest.json` rows gain `truth_issues: list[str]` (unruled slugs
  that explain cells). Draft path text, used by Task 4:
  `<run_date>-<dashboard>-issues/<slug>.md`.

- [ ] **Step 1: Write the failing tests**

```python
def test_comment_names_dashboard_issues_for_the_owner(tmp_path):
    _, result = _truth_run(tmp_path)
    assert cv.comment_text(result["rows"]["1"], result).splitlines()[1:] == [
        "Dashboard issues for the domain owner: tardy_formula (draft, 2 cells).",
        "Nothing else to investigate.",
    ]


def test_comment_gives_a_filed_issue_its_number(tmp_path):
    _, result = _truth_run(tmp_path, lambda d: _add_truth_issue(d, issue=123))
    line = cv.comment_text(result["rows"]["1"], result).splitlines()[1]
    assert line == "Dashboard issues for the domain owner: tardy_formula (#123, 2 cells)."


def test_digest_lists_dashboard_issues_before_cube_additions(tmp_path):
    checks, result = _truth_run(tmp_path)
    md = cv.digest_markdown(result, checks, {})
    assert md.index("## Dashboard, model or source issues") < md.index("## Add to Cube")
    assert "### tardy_formula (dashboard): explains 2 cells in 1 row (# Tardy)" in md
    assert "- Draft: `2026-10-08-demo_dashboard-issues/tardy_formula.md`" in md


def test_digest_has_no_issue_section_without_truth_issues():
    result = cv.run_dashboard(_checks(), FakeCube(), FakeBQ(), TODAY)
    assert "Dashboard, model or source issues" not in cv.digest_markdown(
        result, _checks(), {}
    )


class SameBQ(AltBQ):
    """The variant gives what the dashboard gives: it explains nothing."""

    def __call__(self, sql):
        return [
            dict(r, m0_v0=r["m0"]) if "m0_v0" in r else r for r in super().__call__(sql)
        ]


def test_closed_issue_explaining_nothing_is_stale_and_open_one_is_silent(tmp_path):
    for extra, stale in (({"closed_on": "2026-10-09"}, True), ({}, False)):
        checks = cv.load_checks(
            _write_variant(tmp_path, lambda d: _add_truth_issue(d, **extra))
        )
        result = cv.run_dashboard(checks, FakeCube(), SameBQ(), TODAY)
        assert result["rows"]["1"]["truth_issues"]["tardy_formula"]["stale"] is stale
        md = cv.digest_markdown(result, checks, {})
        assert ("- Stale: the issue is closed" in md) is stale


def test_latest_json_lists_open_truth_issues(tmp_path):
    checks, result = _truth_run(tmp_path)
    cv.write_outputs(result, tmp_path / "out", checks, {})
    latest = json.loads((tmp_path / "out" / "latest.json").read_text())
    assert latest["rows"]["1"]["verdict"] == "truth_issue"
    assert latest["rows"]["1"]["truth_issues"] == ["tardy_formula"]
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "dashboard_issues or filed_issue or stale or open_truth or issue_section" 2>&1 | tail -n 8`
Expected: 6 failures (missing lines, sections and keys).

- [ ] **Step 3: Implement**

Add a helper above `comment_text`:

```python
def _issue_ref(t: dict) -> str:
    return f"#{t['issue']}" if t.get("issue") else "draft"
```

In `comment_text`, after the `if add:` block, add:

```python
    owner = [
        f"{slug} ({_issue_ref(t)}, {t['explains_cells']} cells)"
        for slug, t in row.get("truth_issues", {}).items()
        if t["explains_cells"] and not t["ruling"]
    ]
    if owner:
        lines.append(f"Dashboard issues for the domain owner: {', '.join(owner)}.")
```

and change `elif row["verdict"] == "missing_member":` to
`elif row["verdict"] in ("missing_member", "truth_issue"):`.

In `digest_markdown`, replace the `"## Add to Cube", "",` entries at the end of
the `out += [...]` list with nothing, and right after that list add:

```python
    issues: dict[str, dict] = {}
    for gid, row in rows.items():
        for slug, t in row.get("truth_issues", {}).items():
            i = issues.setdefault(slug, {"cells": 0, "rows": [], "stale": True, **t})
            i["cells"] += t["explains_cells"]
            i["stale"] = i["stale"] and t["stale"]
            if t["explains_cells"]:
                i["rows"].append(gid)
    shown = {s: i for s, i in issues.items() if i["cells"] or i["stale"]}
    if shown:
        out += ["## Dashboard, model or source issues", ""]
        stem = f"{result['run_date']}-{result['dashboard']}"
        for slug, i in sorted(shown.items(), key=lambda kv: -kv[1]["cells"]):
            doc = (checks.get("truth_issues") or {}).get(slug, {})
            names = ", ".join(rows[g]["name"] for g in i["rows"])
            out.append(
                f"### {slug} ({doc.get('where', '?')}): explains "
                f"{_plural(i['cells'], 'cell')} in {_plural(len(i['rows']), 'row')}"
                + (f" ({names})" if names else "")
            )
            if doc.get("title"):
                out.append(f"- {doc['title']}")
            if doc.get("what"):
                out.append(f"- What: {doc['what']}")
            if i["stale"]:
                out.append(
                    "- Stale: the issue is closed and explains no cell now; "
                    "remove its entry."
                )
            elif i.get("issue"):
                call = f", ruled {i['ruling']}" if i.get("ruling") else ", not ruled yet"
                out.append(f"- Issue: #{i['issue']}{call}")
            else:
                out.append(f"- Draft: `{stem}-issues/{slug}.md`")
            out.append("")
    out += ["## Add to Cube", ""]
```

In `report_markdown`, after the `missing_members` block add:

```python
        if row.get("truth_issues"):
            parts = [
                f"{s} ({t['explains_cells']} cells; {_issue_ref(t)}"
                + (f"; {t['ruling']}" if t["ruling"] else "")
                + ")"
                for s, t in row["truth_issues"].items()
            ]
            out += [f"Truth issues: {', '.join(parts)}.", ""]
```

and inside the grain line, after the `explained` addition:

```python
                if g.get("review"):
                    line += f", {g['review']} awaiting the domain owner"
```

In `write_outputs`, add to each `latest["rows"][gid]` dict:

```python
            "truth_issues": sorted(
                s
                for s, t in row.get("truth_issues", {}).items()
                if t["explains_cells"] and not t["ruling"]
            ),
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 184 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): report truth issues in the comment, digest and latest.json

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 4: Issue drafts

**Files:**

- Modify: `scripts/cube_validate.py` (`workbook_exclusions`, `_filters_for`,
  `truth_sql`, `load_checks`, new `live_table`, `_truth_where`, `draft_sql`,
  `issue_drafts`; `write_outputs`; `_run_command`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 2's checks `truth_issues` and summary `examples`; Task 3's
  draft path.
- Produces: `live_table(datasource: str) -> str` (raises `CheckError`), used by
  Task 5.
  `_truth_where(dims, hard_filters, window, truth_filters, datasource, public_only=False) -> list[str]`.
  `issue_drafts(result, checks) -> dict[str, dict]` with `title`,
  `labels: list[str]`, `body: str`. `checks["path"]`.
- Changes: `workbook_exclusions` returns `{"sql": ..., "private": True}` dicts.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------- issue drafts
def test_live_table_reads_the_datasource_caption():
    assert cv.live_table("rpt_tableau__ddi_dashboard (kipptaf_tableau)") == (
        "teamster-332318.kipptaf_tableau.rpt_tableau__ddi_dashboard"
    )
    with pytest.raises(cv.CheckError, match="rpt_demo"):
        cv.live_table("rpt_demo")


def test_issue_draft_follows_the_bug_template(tmp_path):
    checks, result = _truth_run(tmp_path)
    d = cv.issue_drafts(result, checks)["tardy_formula"]
    assert d["title"] == "fix(tableau): the demo dashboard counts half days as tardy"
    assert d["labels"] == ["fix", "tableau", "validation"]
    for part in (
        "## What's happening",
        "## Steps to reproduce",
        "## Where",
        "## How to answer",
        "<summary>For Claude</summary>",
        "2 cells across 1 row",
        "as_written",
        "corrected",
        "# Tardy (1)",
        "`cube-correct`",
        "checks/checks.yml",
    ):
        assert part in d["body"], part


def test_a_filed_issue_gets_no_new_draft(tmp_path):
    checks, result = _truth_run(tmp_path, lambda d: _add_truth_issue(d, issue=123))
    assert cv.issue_drafts(result, checks) == {}


def test_draft_sql_leaves_out_test_record_filters(tmp_path):
    checks, result = _truth_run(tmp_path)
    checks["truth_filters"] = [
        *checks["truth_filters"],
        {"sql": "student_number not in (987654)", "private": True},
    ]
    body = cv.issue_drafts(result, checks)["tardy_formula"]["body"]
    assert "987654" not in body and "student_number not in" not in body


def test_write_outputs_writes_one_draft_per_issue(tmp_path):
    checks, result = _truth_run(tmp_path)
    cv.write_outputs(result, tmp_path / "out", checks, {})
    p = tmp_path / "out" / "2026-10-08-demo_dashboard-issues" / "tardy_formula.md"
    text = p.read_text()
    assert text.startswith("Title: fix(tableau): the demo dashboard")
    assert "Labels: fix, tableau, validation" in text.splitlines()[1]
```

Also change `test_workbook_excludes_read_members_from_the_workbook`'s expected
list to:

```python
    assert cv.workbook_exclusions(checks, FIX / "constructs.twb") == [
        {"sql": "student_name not in ('Student A')", "private": True},
        {"sql": "att_code not in ('X')", "private": True},
    ]
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "live_table or draft or workbook_excludes_read" 2>&1 | tail -n 8`
Expected: 6 failures (no `live_table`, no `issue_drafts`, exclusions still
strings).

- [ ] **Step 3: Implement**

In `workbook_exclusions`, replace the final `out.append(...)` with:

```python
        # private: the members are test-record ids, so no draft or output repeats them.
        out.append({"sql": f"{x['sql']} not in ({values})", "private": True})
```

and its return annotation with `-> list[dict]`.

Replace `_filters_for`:

```python
def _filters_for(truth_filters, datasource: str | None, public_only=False) -> list[str]:
    """Truth filters that apply to one extract: a plain string applies to every one.

    public_only drops the test-record filters, for SQL that leaves this machine.
    """
    out = []
    for f in truth_filters:
        if isinstance(f, str):
            out.append(f)
        elif f.get("datasource") in (None, datasource) and not (
            public_only and f.get("private")
        ):
            out.append(f["sql"])
    return out
```

Move `truth_sql`'s where-clause lines into a helper and call it:

```python
def _truth_where(
    dims, hard_filters, window, truth_filters, datasource, public_only=False
) -> list[str]:
    if isinstance(window, dict):
        years = ", ".join(str(y) for y in window["academic_years"])
        where = [f"{dims['academic_year'].sql_for(datasource)} in ({years})"]
    else:
        where = [
            f"{dims['date'].sql_for(datasource)} between '{window[0]}' and '{window[1]}'"
        ]
    for f in hard_filters:
        values = ", ".join(_sql_literal(v) for v in f["values"])
        where.append(f"{dims[f['dim']].sql_for(datasource)} in ({values})")
    return where + _filters_for(truth_filters, datasource, public_only)
```

In `truth_sql`, replace the lines from `if isinstance(window, dict):` through
`where += _filters_for(truth_filters, datasource)` with
`where = _truth_where(dims, hard_filters, window, truth_filters, datasource)`.

In `load_checks`, before `return data`, add `data["path"] = str(path)`.

Add after `bigquery_rows`:

```python
_CAPTION = re.compile(r"^(\w+) \((\w+)\)$")


def live_table(datasource: str) -> str:
    """The warehouse table behind a datasource captioned `rpt_x (dataset)`."""
    m = _CAPTION.match(datasource)
    if not m:
        raise CheckError(
            f"datasource '{datasource}' is not captioned 'rpt_x (dataset)', so its "
            "warehouse table is unknown"
        )
    return f"{BQ_PROJECT}.{m.group(2)}.{m.group(1)}"
```

Add after `report_markdown`:

````python
def draft_sql(m: dict, v: dict, checks: dict, window) -> str:
    """The dashboard's calculation and its correction, side by side, over the warehouse."""
    try:
        table = live_table(m["datasource"])
    except CheckError:
        table = m["datasource"]
    if m["kind"] == "count":
        cols = [f"{m['sql']} as as_written", f"{v['sql']} as corrected"]
    else:
        cols = [
            f"{m['num']} as as_written_num",
            f"{m['den']} as as_written_den",
            f"{v['num']} as corrected_num",
            f"{v['den']} as corrected_den",
        ]
    where = _truth_where(
        checks["dimensions"],
        checks["hard_filters"],
        window,
        checks["truth_filters"],
        m["datasource"],
        public_only=True,
    )
    # trunk-ignore(bandit/B608): SQL comes from a reviewed checks file and runs read-only
    return f"select {', '.join(cols)}\nfrom `{table}`\nwhere " + "\n  and ".join(where)


def _issue_labels(t: dict) -> list[str]:
    kind = re.match(r"^([a-z]+)", t["title"])
    labels = [kind.group(1)] if kind else []
    labels += {"dashboard": ["tableau"], "rpt": ["dbt"]}.get(t["where"], [])
    return list(dict.fromkeys([*labels, *t["labels"], "validation"]))


def _example_text(c: dict) -> str:
    if c["n_students"] is None or c["n_students"] < SMALL_CELL:
        return "small cell"
    k = c["kind"]
    return (
        f"the dashboard shows {_fmt(c['truth'], k)}, the corrected calculation gives "
        f"{_fmt(c['variant'], k)}, and Cube gives {_fmt(c['cube'], k)}"
    )


def issue_drafts(result, checks) -> dict[str, dict]:
    """One GitHub issue draft per unfiled truth issue that explains cells."""
    window = resolve_window(checks, dt.date.fromisoformat(result["run_date"]))
    out = {}
    for slug, t in (checks.get("truth_issues") or {}).items():
        hits = [
            (gid, row)
            for gid, row in result["rows"].items()
            if row.get("truth_issues", {}).get(slug, {}).get("explains_cells")
        ]
        if t.get("issue") or not hits:
            continue
        cells = sum(row["truth_issues"][slug]["explains_cells"] for _, row in hits)
        m, v = next(
            (m, v)
            for r in checks["rows"]
            for m in r["metrics"]
            for v in m["variants"]
            if slug in v["explains"]
        )
        # The coarsest grains first: a total reads more plainly than a classroom.
        examples = sorted(
            (
                (len(g["grain"]), c)
                for _, row in hits
                for g in row["grains"]
                for s in g.get("metrics", {}).values()
                for c in s.get("examples", [])
                if slug in c["explains"]
            ),
            key=lambda x: x[0],
        )[:3]
        rows_text = ", ".join(f"{row['name']} ({gid})" for gid, row in hits)
        place = {
            "dashboard": f"the Tableau workbook behind {result['dashboard']}",
            "rpt": f"the kipptaf dbt model behind `{m['datasource']}`",
            "source": f"the source data feeding `{m['datasource']}`",
        }[t["where"]]
        body = [
            "## What's happening",
            "",
            t["what"],
            "",
            f"The cube-dashboard validation compared Cube with {result['dashboard']}'s "
            f"extract on {result['run_date']}. With the dashboard's calculation "
            f"corrected, Cube matches it in {_plural(cells, 'cell')} across "
            f"{_plural(len(hits), 'row')}.",
            "",
            *[f"- {' / '.join(c['key']) or 'All'}: {_example_text(c)}." for _, c in examples],
            *(["", t["evidence"]] if t.get("evidence") else []),
            "",
            "## Steps to reproduce",
            "",
            "1. Run this query in BigQuery. `as_written` is the dashboard's calculation "
            "and `corrected` is the fix.",
            "",
            "   ```sql",
            *[f"   {line}" for line in draft_sql(m, v, checks, window).splitlines()],
            "   ```",
            "",
            f"2. Compare both with Cube's `{checks['view']}.{m['cube']}` over the same "
            "filters. Cube matches `corrected`.",
            "",
            "## Where",
            "",
            f"- **Code location / dbt project:** {place}",
            "- **Environment:** prod",
            f"- **Run, PR, or dashboard link (if any):** Asana rows {rows_text}",
            "",
            "## How to answer",
            "",
            "Add one label. `cube-correct` means the dashboard is wrong and Cube's "
            "number is right. `cube-wrong` means the dashboard is right and Cube must "
            "change. If you fix the dashboard or the model instead, close this issue; "
            "the next validation run checks the fix.",
            "",
            "<details>",
            "<summary>For Claude</summary>",
            "",
            f"> Checks file `.claude/skills/cube-dashboard/checks/"
            f"{Path(checks['path']).name}`, truth issue `{slug}`. As written: "
            f"{_metric_sql(m)}. Corrected: {_metric_sql({**v, 'kind': m['kind']})}. "
            "Digest: the run's `-fixes.md` under `~/asana-sync/validation/`.",
            "",
            "</details>",
        ]
        out[slug] = {"title": t["title"], "labels": _issue_labels(t), "body": "\n".join(body)}
    return out
````

In `write_outputs`, before `latest_path = ...`, add:

```python
    drafts = issue_drafts(result, checks) if checks else {}
    for slug, d in drafts.items():
        issues_dir = out_dir / f"{stem}-issues"
        issues_dir.mkdir(exist_ok=True)
        (issues_dir / f"{slug}.md").write_text(
            f"Title: {d['title']}\nLabels: {', '.join(d['labels'])}\n\n{d['body']}\n"
        )
```

In `_run_command`, after the `digest:` print, add:

```python
    drafts = a.out / f"{report.stem}-issues"
    if drafts.exists():
        print(f"issue drafts: {drafts}")
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 189 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): draft one GitHub issue per truth issue for the domain owner

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 5: The `settle` command

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks` settle check; new
  `settle_sql`, `settle_drift`, `settle_text`, `_settle_command`; `main`; module
  docstring)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 4's `live_table`; existing `truth_sql`, `Dim`,
  `download_extract`, `workbook_exclusions`, `ExtractSource`, `bigquery_rows`,
  `resolve_window`, `snapshot_date`.
- Produces: `settle_sql(checks, datasource, table, window) -> str`;
  `settle_drift(extract_rows, live_rows, refreshed: dt.date) -> dict` with
  `days` (list of `{day, age, changes}`), `undated`, `oldest_age`, `recommend`;
  `settle_text(datasource, drift, labels) -> str`; CLI
  `cube_validate.py settle <checks>`.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------- settle
def test_settle_drift_recommends_the_oldest_change_plus_one():
    d = dt.date
    ext = [
        {"g0": d(2026, 10, 1), "m0": 5},
        {"g0": d(2026, 10, 6), "m0": 5},
        {"g0": d(2026, 10, 8), "m0": 3},
        {"g0": None, "m0": 7},
    ]
    live = [
        {"g0": d(2026, 10, 1), "m0": 5},
        {"g0": d(2026, 10, 6), "m0": 6},
        {"g0": d(2026, 10, 8), "m0": 4},
        {"g0": d(2026, 10, 10), "m0": 2},  # after the refresh: settled by any window
        {"g0": None, "m0": 9},  # no date: no cutoff can settle it
    ]
    out = cv.settle_drift(ext, live, d(2026, 10, 9))
    assert [(x["day"], x["age"]) for x in out["days"]] == [
        ("2026-10-06", 3),
        ("2026-10-08", 1),
        ("2026-10-10", -1),
    ]
    assert out["undated"] == {"m0": 2.0}
    assert out["oldest_age"] == 3 and out["recommend"] == 4


def test_settle_drift_with_no_change_recommends_one_day():
    rows = [{"g0": dt.date(2026, 10, 8), "m0": 3}]
    out = cv.settle_drift(rows, rows, dt.date(2026, 10, 9))
    assert out["days"] == [] and out["oldest_age"] is None and out["recommend"] == 1


def test_settle_sql_groups_every_metric_by_the_settle_date(tmp_path):
    def m(d):
        _add_truth_issue(d)
        d["settle"] = {
            "days": 7,
            "date": "calendardate",
            "truth": "calendardate < '{cutoff}'",
            "cube": [],
        }

    c = cv.load_checks(_write_variant(tmp_path, m))
    sql = cv.settle_sql(c, "rpt_demo", "proj.ds.rpt_demo", WINDOW)
    assert "calendardate as g0" in sql and sql.endswith("group by 1")
    assert "sum(is_tardy) as m0" in sql and "sum(is_present) as m1_num" in sql
    assert "_v0" not in sql  # variants are not drift


def test_load_checks_settle_date_is_sql(tmp_path):
    def m(d):
        d["settle"] = {"days": 7, "date": 3, "truth": "x", "cube": []}

    with pytest.raises(cv.CheckError, match="settle needs"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_settle_cli_needs_a_settle_date():
    with pytest.raises(SystemExit, match="settle.date"):
        cv.main(["settle", str(FIX / "checks.yml")])


def test_settle_text_labels_columns_by_metric():
    drift = {
        "days": [{"day": "2026-10-08", "age": 1, "changes": {"m0": 1.0}}],
        "undated": None,
        "oldest_age": 1,
        "recommend": 2,
    }
    text = cv.settle_text("rpt_demo", drift, {"m0": "count_tardy_days"})
    assert "2026-10-08    1  count_tardy_days +1" in text
    assert "days: 2" in text
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k settle 2>&1 | tail -n 8`
Expected: failures for missing `settle_drift`, `settle_sql`, `settle_text`, the
unknown `settle` subcommand, and the accepted non-string date.

- [ ] **Step 3: Implement**

In `load_checks`' settle check, add
`and isinstance(settle.get("date", ""), str)` to the condition, and change the
message to:
`f"{path}: settle needs days (an integer), truth (SQL with {{cutoff}}), cube (filters with {{cutoff}}) and, for the settle command, date (SQL)"`.

Add after `settle_filters`:

```python
def settle_sql(checks: dict, datasource: str, table: str, window) -> str:
    """Every metric on one extract, by the settle date: what drift is measured on."""
    seen: dict[str, dict] = {}
    for r in checks["rows"]:
        for m in r["metrics"]:
            if m["datasource"] == datasource:
                # A variant is a correction, not data: it is not drift.
                seen.setdefault(m["key"], {**m, "variants": []})
    dims = {**checks["dimensions"], "_day": Dim("_day", None, checks["settle"]["date"])}
    return truth_sql(
        table,
        list(seen.values()),
        ["_day"],
        dims,
        checks["hard_filters"],
        window,
        checks["students_sql"],
        checks["truth_filters"],
        datasource,
    )


def settle_drift(extract_rows, live_rows, refreshed: dt.date) -> dict:
    """Which days changed between the extract and the live table, by age."""

    def by_day(rows):
        return {
            norm_key(r["g0"]): {k: _num(v) or 0.0 for k, v in r.items() if k != "g0"}
            for r in rows
        }

    ext, live = by_day(extract_rows), by_day(live_rows)
    days, undated = [], None
    for day in sorted(set(ext) | set(live)):
        a, b = ext.get(day, {}), live.get(day, {})
        changes = {
            k: b.get(k, 0.0) - a.get(k, 0.0)
            for k in sorted(set(a) | set(b))
            if abs(b.get(k, 0.0) - a.get(k, 0.0)) > 1e-9
        }
        if not changes:
            continue
        if day == "∅":
            undated = changes
            continue
        age = (refreshed - dt.date.fromisoformat(day)).days
        days.append({"day": day, "age": age, "changes": changes})
    # A row dated after the refresh is past the cutoff of any window, so it never
    # sets the window's length.
    past = [x["age"] for x in days if x["age"] >= 0]
    oldest = max(past) if past else None
    return {
        "days": days,
        "undated": undated,
        "oldest_age": oldest,
        "recommend": max(1, (oldest if oldest is not None else 0) + 1),
    }


def settle_text(datasource: str, drift: dict, labels: dict) -> str:
    def changes(c: dict) -> str:
        return "; ".join(f"{labels.get(k, k)} {v:+,.0f}" for k, v in c.items())

    out = [f"{datasource}:", "  day         age  changes"]
    out += [f"  {x['day']}  {x['age']:>3}  {changes(x['changes'])}" for x in drift["days"]]
    if drift["undated"]:
        out.append(f"  rows with no date (no cutoff settles them): {changes(drift['undated'])}")
    oldest = drift["oldest_age"]
    out.append(
        "  oldest change: "
        + (f"{oldest} days before the refresh" if oldest is not None else "none")
        + f"; days: {drift['recommend']}"
    )
    return "\n".join(out)


def _settle_labels(checks: dict, datasource: str) -> dict:
    labels, i = {"n_students": "students"}, 0
    seen = []
    for r in checks["rows"]:
        for m in r["metrics"]:
            if m["datasource"] != datasource or m["key"] in seen:
                continue
            seen.append(m["key"])
            if m["kind"] == "count":
                labels[f"m{i}"] = m["key"]
            else:
                labels[f"m{i}_num"] = f"{m['key']} numerator"
                labels[f"m{i}_den"] = f"{m['key']} denominator"
            i += 1
    return labels
```

Add before `_snippet`:

```python
def _settle_command(a) -> int:
    checks = load_checks(a.checks)
    if not (checks.get("settle") or {}).get("date"):
        sys.exit(
            f"{a.checks}: add settle.date (the SQL for a row's date) before measuring"
        )
    datasources = list(
        dict.fromkeys(m["datasource"] for r in checks["rows"] for m in r["metrics"])
    )
    try:
        tables = {ds: live_table(ds) for ds in datasources}
    except CheckError as e:
        sys.exit(str(e))
    extracts = download_extract(
        checks["extract"]["workbook_luid"], datasources, SCRATCH / checks["dashboard"]
    )
    checks["truth_filters"] = checks["truth_filters"] + workbook_exclusions(
        checks, SCRATCH / checks["dashboard"] / "workbook.twb"
    )
    default_at = extracts[checks["extract"]["datasource"]][1]
    window = resolve_window(checks, snapshot_date(default_at))
    now = dt.datetime.now(default_at.tzinfo)
    recommend, oldest = 1, None
    for ds in datasources:
        hyper, at = extracts[ds]
        with ExtractSource(hyper) as q:
            ext = q(settle_sql(checks, ds, EXTRACT_TABLE, window))
        live = bigquery_rows(settle_sql(checks, ds, tables[ds], window))
        drift = settle_drift(ext, live, snapshot_date(at))
        print(settle_text(ds, drift, _settle_labels(checks, ds)))
        recommend = max(recommend, drift["recommend"])
        if drift["oldest_age"] is not None:
            oldest = max(oldest or 0, drift["oldest_age"])
    hours = round((now - default_at).total_seconds() / 3600)
    print(
        f"\n# settle measured {now.date()}: live tables {hours} hours after the "
        f"extract refresh; oldest change "
        + (f"{oldest} days before it" if oldest is not None else "none")
        + f"; days {recommend}"
    )
    return 0
```

In `main`, add the parser and replace the final dispatch:

```python
    s = sub.add_parser(
        "settle", help="measure how many days before a refresh scores still change"
    )
    s.add_argument("checks")
    a = p.parse_args(argv)
    commands = {"grains": _grains_command, "run": _run_command, "settle": _settle_command}
    return commands[a.cmd](a)
```

Add to the module docstring's usage block:
`    uv run scripts/cube_validate.py settle <checks.yml>` and the sentence
`` `settle` compares each extract with its live warehouse table by date and recommends `settle.days`. ``

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 195 passed.

- [ ] **Step 5: Smoke-test the command on DDI**

Add `date: coalesce(date_taken, administered_at)` under `settle:` in
`.claude/skills/cube-dashboard/checks/ddi_suite_completion.yml`. Write
`tests/test_zz_cube_dashboard_settle.py`:

```python
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ROOT / ".claude/skills/cube-dashboard/checks/ddi_suite_completion.yml"


def test_settle() -> None:
    # The pytest fixture loads the Tableau secrets the download needs.
    cmd = ["uv", "run", "--with", "tableauhyperapi", "scripts/cube_validate.py"]
    cmd += ["settle", str(CHECKS)]
    print("exit", subprocess.run(cmd, cwd=ROOT).returncode)
```

Run:
`uv run pytest tests/test_zz_cube_dashboard_settle.py -s -q --tb=short 2>&1 | tail -n 30`
Expected: a drift table for each of the 2 DDI extracts, then a
`# settle measured` line; `exit 0`. Delete the test file. Record the printed
recommendation for the user; do not change `days` without their approval.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py \
  .claude/skills/cube-dashboard/checks/ddi_suite_completion.yml
git commit -m "feat(cube): a settle command measures how long scores keep changing

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 6: `sync.py` gives `truth_issue` rows `needs-review`

**Files:**

- Modify: `~/asana-sync/sync.py`, `~/asana-sync/RULES.md` (outside the repo, not
  committed)

**Interfaces:**

- Consumes: Task 3's `latest.json` verdict `truth_issue`.

- [ ] **Step 1: Back up**

Run:
`cp ~/asana-sync/sync.py ~/asana-sync/sync.py.bak-2026-10-09-before-needs-review`

- [ ] **Step 2: Edit `sync.py`**

- After `UNVALIDATED = ...`, add
  `NEEDS_REVIEW = "needs-review"  # every gap is a dashboard problem awaiting the domain owner's ruling`.
- Change `VALIDATION_TAG` to
  `{"pass": MATCHED, "fail": MISMATCH, "missing_member": MISMATCH, "truth_issue": NEEDS_REVIEW}`.
- Change `for tag_name in (MATCHED, MISMATCH, UNVALIDATED):` to
  `for tag_name in (MATCHED, MISMATCH, UNVALIDATED, NEEDS_REVIEW):`.
- In the untick reasons, before the
  `if not matched and not failed and not partial:` line, add
  `if verdict == "truth_issue": why.append("a dashboard issue awaits the domain owner")`,
  and change that `if` to
  `if not matched and not failed and not partial and verdict != "truth_issue":`.
- In the docstring's step 5 list, add the line
  `truth_issue                    -> 'needs-review' (the gap is the dashboard's; the domain owner rules on a GitHub issue)`
  and change "removing the other two" to "removing the others".

- [ ] **Step 3: Edit `RULES.md`**

Read it, then add `truth_issue → needs-review` beside the other verdict-to-tag
mappings, in the same style.

- [ ] **Step 4: Check it compiles and maps the verdict**

Run:
`uv run python -I -c "import ast,sys; t=open('/home/vscode/asana-sync/sync.py').read(); ast.parse(t); assert '\"truth_issue\": NEEDS_REVIEW' in t; print('ok')"`
Expected: `ok`. The user runs the preview later; it creates the tag on
`--apply`.

### Task 7: Skill runbook, labels and catalog

**Files:**

- Modify: `.claude/skills/cube-dashboard/SKILL.md`, `scripts/CLAUDE.md`
- GitHub: create 3 labels

- [ ] **Step 1: Create the labels**

Run each (the root CLAUDE.md allowlists `gh api` label creation):

```bash
gh api -X POST repos/TEAMSchools/teamster/labels -f name=validation -f color=5319E7 -f description="A cube-dashboard validation gap for the domain owner to rule on"
gh api -X POST repos/TEAMSchools/teamster/labels -f name=cube-correct -f color=0E8A16 -f description="Ruling: the dashboard is wrong; Cube's number is right"
gh api -X POST repos/TEAMSchools/teamster/labels -f name=cube-wrong -f color=B60205 -f description="Ruling: the dashboard is right; Cube must change"
```

Expected: each returns JSON with the label's `name`. Verify with
`mcp__github__get_label` for each name.

- [ ] **Step 2: Edit SKILL.md**

Read it first. Then:

1. Replace the "Verdicts, strongest first" paragraph with:

   ```markdown
   Verdicts, strongest first: `fail` (a gap nothing explains), `incomplete` (a
   grain errored, or a Tableau construct on the row's sheets is unaccounted),
   `truth_issue` (every gap is explained, and at least one by a dashboard, model
   or source problem the domain owner has not ruled on), `missing_member` (every
   gap is explained by a member Cube lacks), `pass`. Each comment lists the
   missing Cube members and the truth issues, with the cells they explain.
   ```

2. Insert a new step before "Run" (renumber the rest):

   ```markdown
   3. Rulings. For each `truth_issues:` entry with `issue:` and no `ruling:`,
      read the issue with `mcp__github__issue_read` (`get`, then `get_labels`).
      A `cube-correct` or `cube-wrong` label becomes
      `ruling: {call, by: <assignee login, or "unassigned">, on: <today>, note: <first line of the latest comment>}`.
      A closed issue gets `closed_on: <date closed>`. Keep a ruling already in
      the file; if a label contradicts it, tell the user instead of changing it.
      Commit the checks file.
   ```

3. In the "Review" step, add: "Dashboard, model or source issues" comes first:
   each truth issue with the cells it explains and its draft, issue number or
   ruling; a stale one is closed and explains nothing, so remove its entry.

4. After the "Post" step, insert:

   ```markdown
   8. Issues. List each draft in
      `~/asana-sync/validation/<date>-<dashboard>-issues/` with its title and
      cell count; the user picks which to file. For each pick: create it with
      `mcp__github__issue_write` (`title` and `labels` from the draft's first
      two lines, the rest as `body`; keep only labels `mcp__github__get_label`
      finds), check the returned title and labels, create a `#NNNN | <title>`
      subtask under the checks file's `open_issues_task` with
      `mcp__claude_ai_Asana__create_tasks` (`parent` set, unassigned), and write
      `issue: <number>` into the entry. Commit the checks file. The user assigns
      each issue to the domain owner.
   ```

5. In the "Tags" step, add "`truth_issue` → `needs-review`" to the mapping.

6. In "Author a check entry", replace step 6 with:

   ```markdown
   6. When the formula uses a field Cube lacks (a filter on homeroom, say), list
      it under the metric's `missing_members:` and add the same SQL without it
      as `sql_without` (or `num_without`/`den_without`). When the dashboard's
      calculation, its `rpt_` model or the source is what is wrong, describe the
      problem under the file's `truth_issues:` (`title` as a conventional-commit
      issue title, `what`, `where`: `dashboard`, `rpt` or `source`, optional
      `evidence` and `labels`) and give the metric a `variants:` entry with the
      corrected SQL and `explains: [<slug>]`. A variant may explain a member and
      a truth issue together. A cell Cube matches only through a variant is
      explained by the names in its `explains`, not reported as a bug. Set the
      file's `open_issues_task:` to the domain's Open Issues task gid
      (Assessments: `1219086050133309`).
   ```

7. Add an authoring step before "Check the file loads":

   ```markdown
   9. Settle. When the window includes the current school year, set
      `settle.date` to the SQL for a row's date and run
      `scripts/cube_validate.py settle <checks>` in the run template (swap `run`
      for `settle` and drop `--as`). Run it late in the day, after the fact's
      later rebuilds. Put its `# settle measured` line beside `settle:` and its
      recommended `days` in the entry, and show both to the user with the other
      changes. Rerun it when the dashboard's refresh schedule changes.
   ```

- [ ] **Step 3: Edit scripts/CLAUDE.md**

Read it, then change the `cube_validate.py` catalog row's purpose to add, after
the `run` clause:
`` `settle` measures how many days before an extract refresh scores still change, against the live `rpt_` table; ``
and change "writes `~/asana-sync/validation/`" to "writes
`~/asana-sync/validation/`, including one GitHub issue draft per truth issue".

- [ ] **Step 4: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md docs/superpowers/plans/2026-10-09-cube-dashboard-truth-issues-and-settle.md </dev/null 2>&1 | tail -n 5`
Expected: `No issues` (run `trunk fmt` on the files first if prettier flags
them).

- [ ] **Step 5: Commit and push**

```bash
git add .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md
git commit -m "docs(cube): runbook for truth issues, rulings and the settle command

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git push
```

## After the plan

Out of scope here, next in the session: author the DDI truth issues (%
Completion stuck at 100%, the 7 assessments in the wrong year, WPP) and the
measured settle window in the DDI checks files, show them to the user, then
rerun.
