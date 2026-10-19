# Cube validation coverage, gap decisions and follow-ups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 2026-10-19 revision: a must-cover measure list with a
coverage section, analyst decisions on formula gaps backed by probes, trust that
carries across runs, and a skill step that drafts follow-ups for approval.

**Architecture:** New config sections load in `config.py`. Three new modules do
one job each: `probes.py` runs probe SQL over the extract, `coverage.py` turns
cells into 1 line per must-cover entry, `trusted.py` records and reads the last
trusted run. `cells.judge` stays the verdict source; decisions relabel its
formula gaps after probes run. The report gains a coverage section first and a
decisions section; the runbook gains the follow-up step.

**Tech Stack:** Python 3.13, `tableauhyperapi` (Hyper SQL, Postgres dialect),
`google-cloud-bigquery`, PyYAML, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-cube-validate-redesign-design.md`,
section "Revision 2026-10-19: measures to cover, gap decisions, follow-ups".
Read the whole spec; the revision extends it.

## Global Constraints

- Run Python only as `uv run` (tests:
  `uv run --with tableauhyperapi pytest tests/scripts/cube_validate -q`).
- The tool never calls Asana or GitHub. Follow-ups are a skill step.
- Report counts 1 to 9 show as `<10` (`report.small` / `report._mask`).
- No student name, id or row key in the report, the checks file, a commit or any
  GitHub text. Snapshots and `hand_checks.md` stay local.
- Hyper scratch tables are `create temporary table`.
- Display precision: compare with `cells.display_equal(..., fmt)` and
  `cells._half_up`; never at export precision.
- Comments follow `.claude/rules/comments.md`; docstrings follow
  `src/teamster/CLAUDE.md`.
- Stage files by name. Never stage `.devcontainer/tpl/.env.tpl`. Commits end
  with `Refs #5856` and the Co-Authored-By line.

## Review Focus

1. **A probe's SQL fails or returns NULL for a mark.** Expect the probe's report
   line to say so, its proof to fail for that mark, and analysis to finish. Test
   in Task 4.
2. **A decision names a measure or selector value the mapping does not have.**
   Expect `ConfigError` naming the decision. Test in Task 1.
3. **A must-cover entry's column shows on several sheets with mixed verdicts.**
   Expect the status order in the spec (gaps open first). Test in Task 6.
4. **No trusted record exists, or it is for another dashboard.** Expect no
   carry-over and the per-snapshot verdict. Test in Task 7.
5. **A decision whose cells now pass.** Expect "resolved" per cell in the
   decisions section, not a silent pass. Test in Task 5.

---

### Task 1: Config sections and the null selector measure

**Files:**

- Modify: `scripts/cube_validate/config.py`
- Test: `tests/scripts/cube_validate/test_config.py`

**Interfaces:**

- Produces (frozen dataclasses in `config.py`, new `Checks` fields default to
  empty tuples):
  - `MustCover(name: str, source: str, cube: tuple[str, str] | None, column: str, param: tuple[str, str] | None, rows: tuple[str, ...])`
    where `cube` is `(member, view)` and `param` is `(caption, value)`.
  - `Probe(id: str, measure: str, param: tuple[str, str] | None, dashboard: str, candidate: str)`
  - `Decision(measure: str, param: tuple[str, str] | None, owner: str, rule: str, probe: str | None, cuts: tuple[str, ...], sheets: tuple[str, ...], task: str)`
    with `owner` in `DECISION_OWNERS = ("dashboard", "cube", "accepted")`.
  - `Checks.must_cover`, `Checks.probes`, `Checks.decisions`.
  - `ParamValue.measure` may now be `None` when the YAML gives `measure: null`
    explicitly; `config.MISSING` marks "key absent".
  - `MAPPING_EXCLUDED = ("causes", "decisions", "must_cover", "probes")` for
    Task 7's fingerprint.

YAML shapes (one entry each):

```yaml
must_cover:
  - name: Percent Chronic Absenteeism
    source: https://app.asana.com/...
    cube:
      {
        member: pct_chronically_absent,
        view: student_attendance_enrollment_periods_view,
      }
    tableau:
      {
        column: Avg. Attendance Metric,
        param: { Attendance Metric: Chronic Absenteeism },
      }
    rows: []
probes:
  - id: chronic-without-transfer-exclusion
    measure: Avg. Attendance Metric
    param: { Attendance Metric: Chronic Absenteeism }
    dashboard: "select ... from {extract} where {where}"
    candidate: "select ... from {extract} where {where}"
decisions:
  - measure: Avg. Attendance Metric
    param: { Attendance Metric: Chronic Absenteeism }
    owner: dashboard
    rule: The dashboard drops students who transferred out this year.
    probe: chronic-without-transfer-exclusion
    task: ""
```

- [ ] **Step 1: Write failing tests** in `test_config.py`:
  - `test_must_cover_probes_and_decisions_load` — the 3 YAML entries above load
    into the dataclasses with the tuples shown.
  - `test_a_must_cover_member_must_match_the_mapping` — entry `cube` member
    `pct_ontime` for a column mapped to `avg_daily_attendance` raises
    `ConfigError` matching `must_cover.*pct_ontime`.
  - `test_a_decision_needs_a_mapped_measure_and_value` — decision on
    `param: {Attendance Metric: Nope}` raises `ConfigError` matching
    `decisions.*Nope`.
  - `test_a_dashboard_or_cube_decision_names_a_known_probe` — owner `dashboard`
    with `probe: missing` raises; owner `accepted` without `cuts` or `sheets`
    raises matching `accepted`.
  - `test_a_selector_value_may_carry_a_null_measure` —
    `{HS Alt: {measure: null}}` under a swapped measure loads with
    `measure is None`; a value with no `measure` key still raises as today.
- [ ] **Step 2: Run**
      `uv run --with tableauhyperapi pytest tests/scripts/cube_validate/test_config.py -q`.
      Expected: the 5 new tests FAIL.
- [ ] **Step 3: Implement** the loaders `_must_cover(d)`, `_probes(d)`,
      `_decisions(d, sheets, params, probes)` in `config.py` and wire them into
      `load_checks`. The swapped-measure check
      (`params.X.Y: ... needs a measure`) now fires only when the `measure` key
      is absent.
- [ ] **Step 4: Run** the whole suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(cube): load must-cover, probes and decisions`.

### Task 2: Show values the way the dashboard does

**Files:**

- Modify: `scripts/cube_validate/cells.py`,
  `scripts/cube_validate/handchecks.py`, `scripts/cube_validate/cli.py`
- Test: `tests/scripts/cube_validate/test_cells.py`,
  `tests/scripts/cube_validate/test_handchecks.py`

**Interfaces:**

- Produces: `cells.shown(value: str | float | None, fmt: Format | None) -> str`
  ("0.965056526" with `Format(1, True)` gives `"96.5%"`; no format returns the
  value unchanged; `None` gives `"None"`). `cells.Cell` gains
  `fmt: Format | None = None`, set by `judge` from `_format`.
  `handchecks._cell_check` writes both the Tableau and Cube values through
  `shown`.
- [ ] **Step 1: Failing tests:** `test_shown_formats_like_the_dashboard` (values
      above, plus `0.0045` at `Format(1, True)` gives `"0.5%"`);
      `test_cell_hand_check_shows_dashboard_values` (a Cell with
      `fmt=Format(1, True)`, tableau `"0.965056526"`, cube `0.96701` gives steps
      containing `` `96.5%` `` and `` `96.7%` ``).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `shown` and the `fmt` field; `judge` sets it on
      every measure cell.
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit**
      `fix(cube): show hand-check values at the dashboard's precision`.

### Task 3: The swapped measure's formula, and clock risk by content

**Files:**

- Modify: `scripts/cube_validate/workbook.py`,
  `scripts/cube_validate/report.py`, `scripts/cube_validate/preflight.py`,
  `scripts/cube_validate/cli.py`
- Test: `tests/scripts/cube_validate/test_workbook.py`,
  `tests/scripts/cube_validate/test_report.py`,
  `tests/scripts/cube_validate/test_preflight.py`

**Interfaces:**

- Produces:
  - `workbook.measure_formula(twb_text: str, header: str, param: tuple[str, str] | None) -> str | None`:
    the calc behind an export header (`Avg. Attendance Metric` resolves the
    caption `Attendance Metric`). When `param` is given and the formula is an
    `IF/ELSEIF [Parameters].[...] = 'value' THEN [Calc]` chain, returns
    `"<caption of Calc> => <its formula>"` for that value.
  - `report.render` takes `twb_text: str` instead of `formulas: dict`; the
    formula-gap section is keyed by (sheet, measure, cut params) and calls
    `measure_formula`.
  - `preflight.BigQuery.row_hashes(table: str, at: dt.datetime) -> collections.Counter`
    (`farm_fingerprint(to_json_string(t))` per row, time travel `at`).
  - `preflight.changed_rows(bq, table: str, before: str, after: str) -> int`:
    rows in one version and not the other, each read 1 s after its modified
    time.
  - Manifest `clock_risk` becomes `"<table>: <n> of <total> rows changed; ..."`,
    or `"none (rebuilt with the same rows: <tables>)"`, or `"none"`.
- [ ] **Step 1: Failing tests:**
  - `test_measure_formula_follows_the_selector_value` — a twb snippet with an
    `Attendance Metric` calc chaining `'ADA' THEN [is_present]` and
    `'Chronic Absenteeism' THEN [Calculation_9]`, where Calculation_9 is
    captioned `Is Chronic Absentee`, returns `Is Chronic Absentee => ...` for
    `("Attendance Metric", "Chronic Absenteeism")` and the whole chain for
    `None`.
  - `test_formula_gap_section_shows_the_selected_calc` in `test_report.py`.
  - `test_changed_rows_counts_both_sides` with a fake BigQuery whose
    `row_hashes` returns `Counter({1: 1, 2: 1})` then `Counter({1: 1, 3: 1})`;
    expect `2`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** In `cli._run`, after `clock_after`, compute moved
      tables with `preflight.changed`, then `changed_rows` for each; a table
      with 0 changed rows goes in the "same rows" list.
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit**
      `fix(cube): show the selector's formula and count changed rows in clock risk`.

### Task 4: Probes

**Files:**

- Create: `scripts/cube_validate/probes.py`
- Test: `tests/scripts/cube_validate/test_probes.py`

**Interfaces:**

- Consumes: `config.Probe`, `cells.Cell` (with `fmt`), `cells._cut_filters`,
  `cells._pred`, `cells.resolve`, `cells.display_equal`, `cells._half_up`.
- Produces:
  - `ProbeCell(cut: str, sheet: str, dims: dict[str, str], dashboard: float | None, candidate: float | None, reproduces: bool, candidate_matches_cube: bool, error: str = "")`
  - `ProbeResult(probe: str, proven: bool, cells: list[ProbeCell])` where
    `proven` is true when every judged cell has `reproduces`.
  - `run(ws, checks, cells: list[Cell]) -> list[ProbeResult]`: for each probe,
    for each judged cell (verdict pass, coincidental match, row gap or formula
    gap) whose measure and cut params match the probe, fills `{extract}` with
    the attached extract table (`"tab"."Extract"."Extract"`) and `{where}` with
    the defaults, the cut's filters and the cell's dims as predicates on raw
    extract columns (prefix `""`), runs it, and compares at `cell.fmt`.
  - `cells._pred` gains a `prefix: str | None = None` argument; `None` keeps
    `f"{side}_"`.
- [ ] **Step 1: Failing tests** with a tiny Hyper extract (3 students, 2 grades)
      built in the test:
  - `test_a_probe_that_reproduces_the_export_is_proven`
  - `test_a_candidate_matching_cube_is_counted_per_cell`
  - `test_a_probe_with_bad_sql_reports_the_error_and_is_not_proven` (Review
    Focus 1)
  - `test_a_probe_returning_null_does_not_reproduce` (Review Focus 1)
- [ ] **Step 2: Run them.** Expected: FAIL (module missing).
- [ ] **Step 3: Implement** `probes.run`. Catch the Hyper exception per cell
      into `error`; never raise for probe SQL.
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(cube): diagnosis probes over the extract`.

### Task 5: Decisions relabel formula gaps

**Files:**

- Create: `scripts/cube_validate/decisions.py`
- Modify: `scripts/cube_validate/cells.py` (verdict constants),
  `scripts/cube_validate/report.py`
- Test: `tests/scripts/cube_validate/test_decisions.py`,
  `tests/scripts/cube_validate/test_report.py`

**Interfaces:**

- Consumes: `config.Decision`, `probes.ProbeResult`.
- Produces:
  - `cells.FIX_DASHBOARD = "fix-dashboard"`, `cells.FIX_CUBE = "fix-cube"`,
    `cells.ACCEPTED = "accepted difference"`, placed in `ORDER` after
    `FORMULA_GAP`; `report.compared` counts them as judged.
  - `decisions.apply(checks, cells: list[Cell], probes: list[ProbeResult]) -> tuple[list[Cell], list[dict]]`:
    returns relabeled cells and 1 summary per decision:
    `{"decision": str, "owner": str, "relabeled": int, "still_formula_gap": int, "resolved": int, "probe_proven": bool}`.
  - A `dashboard`/`cube` decision relabels a formula-gap cell only when its
    probe is proven and that cell's `candidate_matches_cube`. An `accepted`
    decision relabels formula-gap cells in its `cuts` or `sheets`. A pass cell
    under a decision counts as `resolved`. Row gaps are never relabeled.
  - Report: a `### Decisions` section after cell verdicts, 1 line per summary,
    counts through `small`.
- [ ] **Step 1: Failing tests:**
  - `test_a_proven_probe_relabels_only_the_cells_it_explains` — 3 formula-gap
    cells, candidate matches 2: 2 `fix-dashboard`, 1 stays `formula gap`.
  - `test_an_unproven_probe_relabels_nothing`
  - `test_an_accepted_decision_covers_only_its_cuts`
  - `test_passing_cells_under_a_decision_count_as_resolved` (Review Focus 5)
  - `test_row_gaps_are_never_relabeled`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `decisions.apply` and the report section; call
      `probes.run` then `decisions.apply` in `cli.analyze_snapshot` before
      `handchecks.pick` and `report.render`.
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit**
      `feat(cube): analyst decisions relabel formula gaps their probe explains`.

### Task 6: Coverage section

**Files:**

- Create: `scripts/cube_validate/coverage.py`
- Modify: `scripts/cube_validate/workbook.py`,
  `scripts/cube_validate/report.py`, `scripts/cube_validate/cli.py`
- Test: `tests/scripts/cube_validate/test_coverage.py`,
  `tests/scripts/cube_validate/test_workbook.py`

**Interfaces:**

- Consumes: `config.MustCover`, cells after `decisions.apply`,
  `rows.RowsResult.differing_columns`, `checks.excluded_sheets`.
- Produces:
  - `workbook.sheets_showing(twb_text: str, caption: str) -> list[str]`:
    worksheets whose columns include that caption.
  - `coverage.STATUSES` in the spec's order: `"gaps open"`, `"covered"`,
    `"in the data, not in Cube"`, `"not judged"`, `"not mapped yet"`,
    `"only on sheets with names"`, `"not on these dashboards"`.
  - `coverage.lines(checks, cells, rows_result, twb_text) -> list[dict]`, each
    `{"name", "status", "detail", "source"}`; `detail` carries counts (judged
    cells, gaps, differing rows) or the most common tool-limit reason.
  - "only on sheets with names": every sheet showing it in these dashboards is
    in `excluded_sheets`; `detail` lists their reasons.
  - Report: `## Coverage` right after `## Trust verdict`, 1 table row per line.
- [ ] **Step 1: Failing tests,** 1 per status, plus
      `test_mixed_verdicts_across_sheets_take_gaps_open` (Review Focus 3) and
      `test_rows_differing_still_reads_not_in_cube_with_the_count`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat(cube): coverage line per must-cover measure`.

### Task 7: Trust across runs

**Files:**

- Create: `scripts/cube_validate/trusted.py`
- Modify: `scripts/cube_validate/report.py`,
  `scripts/cube_validate/handchecks.py`, `scripts/cube_validate/cli.py`
- Test: `tests/scripts/cube_validate/test_trusted.py`,
  `tests/scripts/cube_validate/test_handchecks.py`

**Interfaces:**

- Produces:
  - `trusted.code_fingerprint(pkg: Path) -> str`: sha256 over every `*.py` in
    the package, sorted by name.
  - `trusted.mapping_fingerprint(checks_path: Path) -> str`: sha256 of the YAML
    with `config.MAPPING_EXCLUDED` keys removed, dumped with sorted keys.
  - `trusted.kinds(cells, rows_result) -> set[str]`: each verdict, and each
    `"<base> / <cause>"` bucket.
  - `trusted.record(root: Path, snapshot: str, code: str, mapping: str, kinds: set[str]) -> None`
    writes `<SNAPSHOT_ROOT>/<dashboard>/trusted.json`.
  - `trusted.read(root: Path) -> dict | None`.
  - `trusted.carries(record: dict | None, code: str, mapping: str, kinds: set[str]) -> bool`.
  - `report.trust(...)` gains `carried_from: str | None = None`; when given and
    invariants hold, returns
    `"Trusted: carried over from <snapshot> (code and mapping unchanged, no new verdicts)."`.
  - `handchecks.pick(..., known: set[str] | None = None)`: with `known`, picks
    only verdicts and buckets not in it (no random passes).
  - `cli.analyze_snapshot` records when the run is trusted on its own, and
    passes `known` plus `carried_from` when a record carries.
- [ ] **Step 1: Failing tests:**
  - `test_fingerprints_ignore_findings_sections` — editing `causes` keeps the
    mapping fingerprint; editing `filters` changes it.
  - `test_a_new_verdict_stops_the_carry_over`
  - `test_no_record_means_no_carry_over` (Review Focus 4)
  - `test_hand_checks_cover_only_what_is_new`
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the suite. Expected: all pass.
- [ ] **Step 5: Commit**
      `feat(cube): trust carries across runs while code and mapping are unchanged`.

### Task 8: Runbook

**Files:**

- Modify: `.claude/skills/cube-dashboard/SKILL.md`

**Interfaces:**

- Consumes: everything above. No code.

Add, each as a short section, in the runbook's voice:

- **Measures to cover:** given a gap-catalog section or an Asana task link, read
  it (Asana connection or the repo file) and draft `must_cover:`; the analyst
  approves. Each entry's `cube` comes from the catalog's "where" column.
- **Diagnosing a formula gap:** write a probe (`dashboard` reproduces the
  export, `candidate` states the rule); run `analyze`; bring the analyst the
  proof and match counts; record the analyst's decision.
- **Follow-ups:** only from a trusted report. Draft 1 per `dashboard`/`cube`
  decision and per "in the data, not in Cube" line, aggregates only with `<10`.
  Show the draft and post nothing until the analyst approves. Dashboard fix:
  Asana subtask under the measure's subtask, or ask for the parent. Cube fix or
  missing measure: GitHub issue from
  `.github/ISSUE_TEMPLATE/feature_request.md`. Put the link in the decision's
  `task`. Asana tags are set by hand.
- **Trust across runs:** what carries and what brings hand checks back.
- **Reusing a snapshot:** every step after capture runs on a frozen snapshot; a
  change that needs new exports or answers says so and waits for an evening
  capture.

- [ ] **Step 1: Edit** SKILL.md. Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md </dev/null`.
      Expected: no issues beyond formatting.
- [ ] **Step 2: Commit**
      `docs(cube): runbook steps for coverage, decisions and follow-ups`.

### Task 9: Rehearsal setup for a fresh analyst session

**Files:**

- Create:
  `.claude/skills/cube-dashboard/checks/attendance_dashboard.rehearsal.yml`
  (gitignored copy; add the pattern `*.rehearsal.yml` under the checks folder to
  `.gitignore`)
- Modify: `.gitignore`

**Interfaces:**

- Consumes: the committed checks file and snapshot `2026-10-19T2025`.

- [ ] **Step 1:** Copy the committed checks file to the rehearsal file with
      `causes`, `decisions`, `must_cover` and `probes` emptied; keep
      `dashboard: attendance_dashboard` so it finds the snapshot root.
- [ ] **Step 2:** Copy the snapshot so the rehearsal never touches the real
      one's report or hand checks:
      `cp -r ~/.cache/cube-validate/attendance_dashboard/2026-10-19T2025 ~/.cache/cube-validate/attendance_dashboard/2026-10-19T2025-rehearsal`,
      then delete the copy's `analysis/` folder.
- [ ] **Step 3: Verify**
      `uv run --with tableauhyperapi python -m scripts.cube_validate analyze .claude/skills/cube-dashboard/checks/attendance_dashboard.rehearsal.yml --snapshot ~/.cache/cube-validate/attendance_dashboard/2026-10-19T2025-rehearsal`
      writes a report whose rows read "unexplained" where causes used to claim
      them, and that the real snapshot's `analysis/report.md` is unchanged
      (compare `sha256sum` before and after).
- [ ] **Step 4: Write** the opening prompt for the fresh session into
      `/home/vscode/.cache/cube-validate/attendance_dashboard/REHEARSAL.md`
      (local only): use the `cube-dashboard` skill; checks file is the rehearsal
      copy; snapshot `2026-10-19T2025-rehearsal` is frozen and must not be
      recaptured; any step that needs new exports or answers is reported as
      "needs a capture" and skipped; the measure list comes from Asana task
      1213823788919470; post nothing to Asana or GitHub.
- [ ] **Step 5: Commit** the `.gitignore` change:
      `chore(cube): ignore rehearsal checks files`.
