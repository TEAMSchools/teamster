# Cube issues and related-issue search: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A gap Cube's own formula causes gets a `cube_issue` verdict, a "Fix in
Cube" digest section and a drafted GitHub issue; and every draft and unexplained
gap is checked against existing issues before anything is filed.

**Architecture:** `cube_issues:` sits beside `truth_issues:` in the checks file
and reuses the variant machinery: a variant naming a cube issue copies Cube's
formula over the extract. The script stays offline; the related-issue search is
a skill step.

**Tech Stack:** Python 3.13, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-cube-validate-skill-design.md`,
revision "cube issues prove Cube's formula differs", including its "Related
issues" section.

## Global Constraints

- Always `uv run`. The suite is
  `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5` (200
  pass at the start).
- No student or staff names or ids in any output, draft, comment or commit.
- The script never calls GitHub or Asana.
- Stage files by name. Never stage
  `.claude/skills/cube-dashboard/checks/state_testing_analysis_tool.yml` or
  `.devcontainer/tpl/.env.tpl`.
- Open files under `.claude/` with the Read tool.
- Before pushing markdown or YAML, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- Commit messages end with
  `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- `~/asana-sync/sync.py` is outside the repo: back it up before editing.
- The `cube` and `validation` labels exist.

## Review Focus

- A slug used as both a truth issue and a cube issue, or as a missing member,
  must stop the load. Task 1 tests it.
- A cell explained by a cube issue and a missing member together counts for
  both. Task 1 tests it.
- A filed cube issue (`issue:` set) gets no second draft. Task 3 tests it.
- A draft's `Related:` line shows only the numbers in the entry's `related:`.
  Task 3 tests it.
- A truth issue ruled `cube-correct` must not hide a cube issue on the same
  cell's variant. Task 1 tests it.

---

### Task 1: `cube_issues` in the checks file and the `cube_issue` verdict

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks`, `summarize`, `row_verdict`,
  `run_dashboard`, `_COMPARED`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `checks["cube_issues"]: dict[str, dict]` (each with `title`, `what`,
  `labels: list`, `related: list[int]`, optional `issue`, `closed_on`,
  `evidence`); truth issues also gain `related: list[int]`.
- Produces: `summarize(..., cube_issues=frozenset())` adds `cube` (explained
  cells naming a cube issue). Grain entries carry `cube`. Grain status and row
  verdict can be `cube_issue`. Result rows may carry
  `cube_issues: {slug: {explains_cells, issue, stale}}`.

- [ ] **Step 1: Write the failing tests**

```python
# ---------------------------------------------------------------- cube issues
def _add_cube_issue(d, **extra):
    d["cube_issues"] = {
        "rows_not_pairs": {
            "title": "fix(cube): count_tardy_days counts rows, not tardy days",
            "what": "Cube's measure counts every row where the dashboard counts days.",
            **extra,
        }
    }
    d["rows"][0]["metrics"][0]["variants"] = [
        {"explains": ["rows_not_pairs"], "sql": "countif(att_code = 'T')"}
    ]


def test_cube_issue_makes_the_row_cube_issue(tmp_path):
    _, result = _truth_run(tmp_path, _add_cube_issue)
    row = result["rows"]["1"]
    assert row["verdict"] == "cube_issue"
    school = next(g for g in row["grains"] if g["grain"] == ["region", "school"])
    assert school["status"] == "cube_issue" and school["cube"] == 2
    assert row["cube_issues"] == {
        "rows_not_pairs": {"explains_cells": 2, "issue": None, "stale": False}
    }


def test_a_slug_is_one_kind_of_thing(tmp_path):
    def m(d):
        _add_cube_issue(d)
        _add_truth_issue(d)
        d["truth_issues"]["rows_not_pairs"] = d["truth_issues"].pop("tardy_formula")

    with pytest.raises(cv.CheckError, match="rows_not_pairs.*more than one"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_a_cube_issue_slug_is_not_a_missing_member(tmp_path):
    def m(d):
        _add_cube_issue(d)
        d["rows"][0]["metrics"][0]["missing_members"] = ["rows_not_pairs"]

    with pytest.raises(cv.CheckError, match="rows_not_pairs.*more than one"):
        cv.load_checks(_write_variant(tmp_path, m))


def test_a_cube_issue_and_a_member_explain_a_cell_together(tmp_path):
    def m(d):
        _add_cube_issue(d)
        mm = d["rows"][0]["metrics"][0]
        mm["missing_members"] = ["team"]
        mm["variants"][0]["explains"] = ["rows_not_pairs", "team"]

    _, result = _truth_run(tmp_path, m)
    row = result["rows"]["1"]
    assert row["verdict"] == "cube_issue"
    assert row["missing_members"]["team"]["explains_cells"] == 2


def test_an_accepted_truth_issue_does_not_hide_a_cube_issue(tmp_path):
    ruling = {"call": "cube-correct", "by": "owner", "on": "2026-10-09"}

    def m(d):
        _add_truth_issue(d, ruling=ruling)
        _add_cube_issue(d)
        d["rows"][0]["metrics"][0]["variants"] = [
            {"explains": ["tardy_formula", "rows_not_pairs"], "sql": "countif(att_code = 'T')"}
        ]

    _, result = _truth_run(tmp_path, m)
    assert result["rows"]["1"]["verdict"] == "cube_issue"


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        (["cube_issue", "truth_issue"], "cube_issue"),
        (["cube_issue", "fail"], "fail"),
        (["cube_issue", "error"], "incomplete"),
    ],
)
def test_row_verdict_cube_issue(statuses, verdict):
    assert cv.row_verdict([{"status": s} for s in statuses]) == verdict
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "cube_issue or one_kind or not_a_missing or hide_a_cube" 2>&1 | tail -n 10`
Expected: failures on unknown variant names (`rows_not_pairs`), missing
`cube`/`cube_issues` keys and verdicts that are not `cube_issue`.

- [ ] **Step 3: Implement**

In `load_checks`, after the truth-issue loop (before
`data["truth_issues"] = issues`), add
`t["related"] = list(t.get("related") or [])` inside that loop, then after it:

```python
    # Gaps Cube's own formula causes: its variant copies Cube's definition.
    cube_issues = data.get("cube_issues") or {}
    if not isinstance(cube_issues, dict):
        raise CheckError(f"{path}: cube_issues is a map of slug to entry")
    for slug, t in cube_issues.items():
        at = f"{path}: cube issue '{slug}'"
        missing = [k for k in ("title", "what") if not (t or {}).get(k)]
        if missing:
            raise CheckError(f"{at} is missing {missing}")
        if t.get("issue") is not None and not isinstance(t["issue"], int):
            raise CheckError(f"{at}: issue is the GitHub issue number")
        t["labels"] = list(t.get("labels") or [])
        t["related"] = list(t.get("related") or [])
    data["cube_issues"] = cube_issues
```

In the variant name check, change `known = set(issues) | ...` to
`known = set(issues) | set(cube_issues) | set(m.get("missing_members") or [])`,
and before the `for v in variants:` loop add:

```python
            names = [*issues, *cube_issues, *(m.get("missing_members") or [])]
            twice = sorted({n for n in names if names.count(n) > 1})
            if twice:
                raise CheckError(
                    f"{where}: {', '.join(twice)} is named as more than one of a "
                    "truth issue, a cube issue and a missing member"
                )
```

(`cube_issues` must be parsed before the rows loop, next to `issues`.)

In `summarize`, add the parameter `cube_issues=frozenset()` and the output key
`"cube": sum(1 for c in explained if set(c.explained_by) & cube_issues),`.
Change `is_accepted` so a cube issue is never accepted:

```python
    def is_accepted(c):
        names = set(c.explained_by)
        return c.explained and names <= accepted and not names & cube_issues
```

In `row_verdict`, change the loop to
`for s in ("cube_issue", "truth_issue", "missing_member"):`.

In `run_dashboard`, add `cube_slugs = frozenset(checks["cube_issues"])` next to
`issue_states`, pass `cube_issues=cube_slugs` to `summarize`, and in the grain
status:

```python
                cube = sum(s["cube"] for s in ms.values())
                entry.update(
                    status="fail"
                    if bad
                    else "cube_issue"
                    if cube
                    else "truth_issue"
                    if review
                    else ("missing_member" if explained else "pass"),
                    ...,
                    cube=cube,
```

Add `"cube_issue"` to the audit tuple and to `_COMPARED`. After the `truth`
block, add:

```python
        cube_found = {}
        for slug in sorted(
            {
                n
                for m in row["metrics"]
                for v in m["variants"]
                for n in v["explains"]
                if n in checks["cube_issues"]
            }
        ):
            t = checks["cube_issues"][slug]
            n = sum(
                s["explained_by"].get(slug, 0)
                for g in grains
                for s in g.get("metrics", {}).values()
            )
            cube_found[slug] = {
                "explains_cells": n,
                "issue": t.get("issue"),
                "stale": bool(t.get("closed_on")) and not n,
            }
```

and `**({"cube_issues": cube_found} if cube_found else {}),` to the row dict.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 208 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a cube_issue verdict for gaps Cube's own formula causes

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 2: "Fix in Cube" in the comment, digest, report and latest.json

**Files:**

- Modify: `scripts/cube_validate.py` (`comment_text`, `digest_markdown`,
  `report_markdown`, `write_outputs`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 1's row `cube_issues`.
- Produces: `latest.json` rows gain `cube_issues: list[str]` (slugs that explain
  cells).

- [ ] **Step 1: Write the failing tests**

```python
def test_comment_says_what_to_fix_in_cube(tmp_path):
    _, result = _truth_run(tmp_path, _add_cube_issue)
    assert cv.comment_text(result["rows"]["1"], result).splitlines()[1:] == [
        "Fix in Cube: rows_not_pairs (draft, 2 cells).",
        "Nothing else to investigate.",
    ]


def test_digest_puts_fix_in_cube_first(tmp_path):
    checks, result = _truth_run(tmp_path, _add_cube_issue)
    md = cv.digest_markdown(result, checks, {})
    assert md.index("## Fix in Cube") < md.index("## Add to Cube")
    assert "### rows_not_pairs: explains 2 cells in 1 row (# Tardy)" in md
    assert "- Dashboard: `sum(is_tardy)`" in md
    assert "- Cube, reproduced over the extract: `countif(att_code = 'T')`" in md
    assert "- Draft: `2026-10-08-demo_dashboard-issues/rows_not_pairs.md`" in md


def test_latest_json_lists_cube_issues(tmp_path):
    checks, result = _truth_run(tmp_path, _add_cube_issue)
    cv.write_outputs(result, tmp_path / "out", checks, {})
    latest = json.loads((tmp_path / "out" / "latest.json").read_text())
    assert latest["rows"]["1"]["verdict"] == "cube_issue"
    assert latest["rows"]["1"]["cube_issues"] == ["rows_not_pairs"]
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "fix_in_cube or lists_cube" 2>&1 | tail -n 6`
Expected: 3 failures.

- [ ] **Step 3: Implement**

In `comment_text`, after the `wrong` block:

```python
    fix = [
        f"{slug} ({_issue_ref(t)}, {t['explains_cells']} cells)"
        for slug, t in row.get("cube_issues", {}).items()
        if t["explains_cells"]
    ]
    if fix:
        lines.insert(1, f"Fix in Cube: {', '.join(fix)}.")
```

and change the verdict tuple to
`("missing_member", "truth_issue", "cube_issue")`.

In `digest_markdown`, insert before the `issues: dict[str, dict] = {}` block:

```python
    defs_by_slug: dict[str, tuple[dict, dict]] = {}
    for r in checks.get("rows", []):
        for m in r["metrics"]:
            for v in m.get("variants", []):
                for n in v["explains"]:
                    defs_by_slug.setdefault(n, (m, v))
    fixes: dict[str, dict] = {}
    for gid, row in rows.items():
        for slug, t in row.get("cube_issues", {}).items():
            i = fixes.setdefault(slug, {"cells": 0, "rows": [], "stale": True, **t})
            i["cells"] += t["explains_cells"]
            i["stale"] = i["stale"] and t["stale"]
            if t["explains_cells"]:
                i["rows"].append(gid)
    shown_fix = {s: i for s, i in fixes.items() if i["cells"] or i["stale"]}
    if shown_fix:
        out += ["## Fix in Cube", ""]
        stem = f"{result['run_date']}-{result['dashboard']}"
        for slug, i in sorted(shown_fix.items(), key=lambda kv: -kv[1]["cells"]):
            doc = (checks.get("cube_issues") or {}).get(slug, {})
            names = ", ".join(rows[g]["name"] for g in i["rows"])
            out.append(
                f"### {slug}: explains {_plural(i['cells'], 'cell')} in "
                f"{_plural(len(i['rows']), 'row')}" + (f" ({names})" if names else "")
            )
            for key, label in (("title", None), ("what", "What")):
                if doc.get(key):
                    out.append(f"- {label + ': ' if label else ''}{doc[key]}")
            if slug in defs_by_slug:
                m, v = defs_by_slug[slug]
                out.append(f"- Dashboard: {_metric_sql(m)}")
                out.append(
                    "- Cube, reproduced over the extract: "
                    f"{_metric_sql({**v, 'kind': m['kind']})}"
                )
            if i["stale"]:
                out.append(
                    "- Stale: the issue is closed and explains no cell now; "
                    "remove its entry."
                )
            elif i.get("issue"):
                out.append(f"- Issue: #{i['issue']}")
            else:
                out.append(f"- Draft: `{stem}-issues/{slug}.md`")
            out.append("")
```

In `report_markdown`, after the `truth_issues` block:

```python
        if row.get("cube_issues"):
            parts = [
                f"{s} ({t['explains_cells']} cells; {_issue_ref(t)})"
                for s, t in row["cube_issues"].items()
            ]
            out += [f"Cube issues: {', '.join(parts)}.", ""]
```

In `write_outputs`, add to each latest row:

```python
            "cube_issues": sorted(
                s for s, t in row.get("cube_issues", {}).items() if t["explains_cells"]
            ),
```

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 211 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a Fix in Cube section for cube issues

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 3: Cube-issue drafts and `Related:` lines

**Files:**

- Modify: `scripts/cube_validate.py` (`draft_sql`, `_issue_labels`,
  `_example_text`, `issue_drafts`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: Task 1's `checks["cube_issues"]`, `related` on both kinds.
- Changes: `draft_sql(m, v, checks, window, alias="corrected")`;
  `_issue_labels(t, kind="truth")`; `_example_text(c, kind="truth")`.
  `issue_drafts` returns drafts for both kinds, keyed by slug.

- [ ] **Step 1: Write the failing tests**

```python
def test_cube_issue_draft_asks_for_a_cube_fix(tmp_path):
    checks, result = _truth_run(tmp_path, _add_cube_issue)
    d = cv.issue_drafts(result, checks)["rows_not_pairs"]
    assert d["labels"] == ["fix", "cube", "validation"]
    for part in (
        "cube_formula",
        "as_written",
        "Cube's formula over the extract gives",
        "Fix the Cube definition",
        "`demo_view.count_tardy_days`",
    ):
        assert part in d["body"], part
    assert "cube-correct" not in d["body"]


def test_a_filed_cube_issue_gets_no_new_draft(tmp_path):
    checks, result = _truth_run(tmp_path, lambda d: _add_cube_issue(d, issue=77))
    assert cv.issue_drafts(result, checks) == {}


def test_drafts_list_only_the_related_issues_named(tmp_path):
    checks, result = _truth_run(tmp_path, lambda d: _add_truth_issue(d, related=[3801, 5668]))
    body = cv.issue_drafts(result, checks)["tardy_formula"]["body"]
    assert "Related: #3801, #5668" in body
    plain_checks, plain = _truth_run(tmp_path)
    plain_body = cv.issue_drafts(plain, plain_checks)["tardy_formula"]["body"]
    assert "Related:" not in plain_body
```

- [ ] **Step 2: Run them to watch them fail**

Run:
`uv run pytest tests/scripts/test_cube_validate.py -q -k "cube_fix or filed_cube or related_issues" 2>&1 | tail -n 6`
Expected: 3 failures (no cube drafts; no `Related:` line).

- [ ] **Step 3: Implement**

- `draft_sql`: add `alias="corrected"` and use it in place of `corrected` in the
  column names.
- `_issue_labels(t, kind="truth")`: when `kind == "cube"`, the middle labels are
  `["cube"]` instead of the `where` lookup.
- `_example_text(c, kind="truth")`: when `kind == "cube"`, the middle phrase is
  `"Cube's formula over the extract gives"` instead of
  `"the corrected calculation gives"`.
- `issue_drafts`: loop over
  `[("truth", s, t) for s, t in truth.items()] + [("cube", s, t) for s, t in cube.items()]`,
  reading hits from
  `row.get("truth_issues" if kind == "truth" else "cube_issues", {})`. For
  `kind == "cube"`:
  - the opening sentence:
    `f"The cube-dashboard validation compared Cube with {result['dashboard']}'s extract on {result['run_date']}. In {_plural(cells, 'cell')} across {_plural(len(hits), 'row')}, Cube gives what its own formula gives over the extract, and the dashboard shows something else."`;
  - the query alias `cube_formula`, with step 1 saying "`as_written` is the
    dashboard's calculation and `cube_formula` is Cube's, over the same rows."
    and step 2 "Cube matches `cube_formula`.";
  - `place = f"the Cube definition of \`{checks['view']}.{m['cube']}\` under
    src/cube/model"`;
  - "How to answer":
    `"Fix the Cube definition to compute what the dashboard shows, then close this issue; the next validation run checks the fix. If you think the dashboard is the one that is wrong, say so in a comment."`
    For both kinds, after the examples, add
    `*([f"", f"Related: {', '.join(f'#{n}' for n in t['related'])}"] if t["related"] else [])`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest tests/scripts/test_cube_validate.py -q 2>&1 | tail -n 5`
Expected: 214 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): draft cube issues, and name related issues in every draft

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

### Task 4: `sync.py`, SKILL.md and the catalog

**Files:**

- Modify: `~/asana-sync/sync.py`, `~/asana-sync/RULES.md` (outside the repo)
- Modify: `.claude/skills/cube-dashboard/SKILL.md`, `scripts/CLAUDE.md`

- [ ] **Step 1: sync.py**

Back up to `~/asana-sync/sync.py.bak-2026-10-09-before-cube-issue`. Then:

- `VALIDATION_TAG` gains `"cube_issue": MISMATCH`.
- In the untick reasons, add
  `if verdict == "cube_issue": why.append("Cube's formula differs from the dashboard")`,
  and add `and verdict != "cube_issue"` to the "not validated" condition.
- In the docstring's step 5, add `cube_issue -> 'mismatch'` to the
  `fail, missing_member` line.

Add `cube_issue` to the `mismatch` line in `RULES.md`.

Check:
`uv run python -I -c "import ast; t=open('/home/vscode/asana-sync/sync.py').read(); ast.parse(t); assert '\"cube_issue\": MISMATCH' in t; print('ok')"`
Expected: `ok`.

- [ ] **Step 2: SKILL.md**

Read it first. Then:

1. The verdict paragraph: insert `cube_issue` (every gap is explained, at least
   one by Cube's own formula) after `incomplete`.
2. The Review step: "Fix in Cube" comes first, then "Dashboard, model or source
   issues". Then add: "Before the user picks anything to file, search the repo's
   issues (open and closed) with `mcp__github__search_issues` for each draft and
   each row under Investigate: the problem in plain words, the metric, the
   models and the dashboard. List the matches beside each. The same problem
   becomes the entry's `issue:` instead of a new filing; a related one goes in
   the entry's `related:` (rerun or edit the draft so its `Related:` line shows
   it)."
3. The Issues step: "Each draft" now covers cube issues too.
4. The Tags step: `cube_issue` → `mismatch`.
5. Authoring step 6: after the truth-issue sentence, add: "When Cube's own
   formula is what differs (it counts rows where the dashboard counts students,
   say), describe it under `cube_issues:` (`title`, `what`, optional `evidence`,
   `labels`, `related`) and give the metric a variant whose SQL copies Cube's
   definition over the extract, with `explains: [<slug>]`. A slug names one
   thing only: a truth issue, a cube issue or a missing member."

- [ ] **Step 3: scripts/CLAUDE.md**

Read the `cube_validate.py` row, then change "one GitHub issue draft per truth
issue" to "one GitHub issue draft per truth or cube issue".

- [ ] **Step 4: Lint, commit, push**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md docs/superpowers/plans/2026-10-09-cube-dashboard-cube-issues.md </dev/null 2>&1 | tail -n 3`
Expected: `No issues` (run `trunk fmt` on them first if prettier flags them).

```bash
git add .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md
git commit -m "docs(cube): runbook for cube issues and the related-issue search

Refs #4314

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
git push
```

## After the plan

Link the DDI year problem to #3801 instead of drafting it, after checking its
assessments are ours; note #4167, #4168 and #4176 against the DDI missing
members; then test the distinct-pairs suspicion on % Complete as the first cube
issue.
