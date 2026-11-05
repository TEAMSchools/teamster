# Cube Validation: Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A command-line validator that compares each Cube measure with its
dashboard, a source anchor, or its sibling measures, at 1 shared moment rebuilt
from BigQuery, and hands the analyst a triage list.

**Architecture:** A Python package `scripts/cube_validation/` builds BigQuery
SQL for both sides "as of" a Cube fact build (time travel, views expanded to
base tables, clock functions pinned) and runs every comparison inside BigQuery,
so student-level rows never leave the warehouse. Per-view configuration and the
analyst's recorded decisions live in `src/cube/validation/<view>.yml`. Tableau
is touched only to prove a workbook formula once, through a copy in `TEMP-CB`.

**Tech Stack:** Python 3.13 (`uv run`), `google-cloud-bigquery` (ADC),
`tableauserverclient`, `pyyaml`, stdlib `hmac`/`urllib` for Cube REST, pytest.

**Spec:**
`docs/superpowers/specs/2026-10-26-cube-validation-and-build-skill-design.md`
(Part 1 only). Carried-over rules:
`docs/superpowers/specs/2026-10-26-cube-validation-approved-rules.md`. Issue
#6150.

Worktree:
`/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-cube-validation-and-build-skill`
(`W` below). Run every command with `cd W &&` first, and `git -C W` for git. IDE
Pyright errors on worktree files are false positives; trust `uv run`.

## Global Constraints

- No production change: no extract refresh, no schedule change, no Tableau
  content written outside the `TEMP-CB` project.
- The tool never posts to Slack. Anything posted to GitHub shows counts under 10
  as `<10`. Row-level output never leaves local files or BigQuery; nothing
  committed names a person.
- Every comparison runs inside the 7-day time-travel window of its moment.
- The compiled SQL is the raw query, not Cube's 1 pre-aggregation.
- The Cube token's email must have the `network` grant; refuse if the compiled
  school filter lists fewer schools than the network scope.
- Each Cube view in scope reads 1 fact; a measure that reads 2 facts is refused.
- Decisions live in `src/cube/validation/<view>.yml`, never under
  `src/cube/model/`.
- Build fresh: do not port code from the deleted first tool (closed PR #5961).
- Each run prices its queries with BigQuery dry runs first and states the cost;
  `--max-usd` defaults to 5.
- Commands that need the Tableau PAT or `CUBE_API_SECRET` run under the pytest
  secrets fixture through a throwaway `tests/test_zz_cube_validation.py`, with
  `--tb=short`. BigQuery uses ADC and needs no fixture.
- No new `pyproject.toml` dependencies. Cube's JWT is signed with stdlib `hmac`;
  HTTP uses `urllib.request`.
- Never bare `uv run pytest`: run `uv run pytest tests/scripts/cube_validation`
  only (`tests/` holds live integration tests).

## Review Focus

1. A view in the dashboard's lineage changed its SQL after the moment: the
   rebuild must use the view's SQL as it stood then (from `CREATE VIEW` jobs),
   not today's. Test in Task 3.
2. No fact build inside the time-travel window, or `--moment` older than 7 days:
   a plain refusal naming the window, not a BigQuery error. Test in Task 3.
3. Compiled SQL that reads the pre-aggregation, reads 2 facts, or carries a
   short school list: refused with the reason. Test in Task 4.
4. A Google Sheets external table in the lineage: read live and named in the
   result, never silent. Test in Task 2.
5. A decision whose SQL changed only in whitespace or comments stays quiet; a
   logic change asks for re-confirmation. Test in Task 6.

---

## File Structure

```text
scripts/cube_validation/
  __init__.py
  __main__.py        # python -m scripts.cube_validation <command>
  config.py          # load and validate src/cube/validation/<view>.yml
  timetravel.py      # as-of SQL rewriting: refs, views, clock pinning
  bq.py              # BigQuery client, catalog, JOBS queries, cost guard
  moment.py          # fact builds, moment choice, table fingerprints
  cube_client.py     # Cube token, compiled SQL, parameter binding, refusals
  compare.py         # row reconcile, scope, cells, groups, clauses
  decisions.py       # fingerprints and applying recorded decisions
  checks.py          # anchors, identities, strongest check per measure
  tableau.py         # workbook copy, number formats, exports, proof
  discover.py        # candidate comparisons from exposures and calcs
  report.py          # local result, GitHub masking, review-issue body
  cli.py             # commands: discover, prove, check-api, run, review
src/cube/validation/
  student_attendance_enrollment_daily_view.yml   # first real file (Task 13)
tests/scripts/cube_validation/
  test_<module>.py   # 1 per module, offline, fakes only
  fixtures/          # SQL and .twb snippets, no student data
.claude/skills/cube-validation/SKILL.md          # analyst runbook (Task 13)
```

## The validation file (shared by Tasks 1 and 5 to 12)

```yaml
view: student_attendance_enrollment_daily_view
fact: kipptaf_marts.fct_student_attendance_enrollment_daily
email: someone@apps.teamschools.org # network grant; overridable by --email
comparisons:
  - id: ada-y1-region
    measure: avg_daily_attendance
    confirmed: true
    workbook: 87c13e78-a912-40a4-95dd-33248fc1cbd3
    sheet: Y1 ADA - Region
    dashboard_view: kipptaf_tableau.rpt_tableau__attendance_dashboard
    probe: avg(is_present) # aggregate over dashboard rows; or probe_sql
    decimals: 3 # digits of the compared value: p0.0% is a fraction to 3; Task 8 fills it
    dims: # sheet dims, dashboard column -> Cube member
      - { dashboard: region, cube: regions_region_name }
    filters: # filter card caption -> both sides
      Academic Year: { dashboard: academic_year, cube: dates_academic_year }
      Region: { dashboard: region, cube: regions_region_name }
    defaults: { Academic Year: "2026", Region: [Camden, Newark, Paterson] }
    cuts: [{}, { Region: Miami }]
    scope: [] # e.g. { cube: grade_level, values: [...] }
    rows: # row-level reconcile; grain first
      grain:
        - { dashboard: student_number, cube: lea_student_identifier }
        - { dashboard: calendardate, cube: attendance_date }
      values:
        - { dashboard: is_present, cube: attendance_value }
    proof: null # written by `prove`: fingerprint, cells, proven_at
anchors:
  - measure: avg_daily_attendance
    value: 0.912
    source: PowerSchool ADA report
    as_of: 2026-10-15
    date_range: [2026-08-12, 2026-10-15]
    filters: { regions_region_name: Newark }
identities:
  - name: ada-is-attendance-over-membership
    left: avg_daily_attendance
    right: sum_attendance_value / sum_membership_value
decisions:
  - id: example
    comparison: ada-y1-region
    group: { column: grade_level, values: ["9"] }
    call: deliberate # deliberate | fix_dashboard | fix_cube | domain_owner
    reason: ...
    task: "" # Asana or GitHub link for fix_* and domain_owner
    fingerprints: { cube: <sha256>, dashboard: <sha256> }
```

`probe_sql` (alternative to `probe`) is a full query template with `{rows}`,
`{where}` and `{dims}` placeholders, for detail-level calculations.

---

### Task 1: Package skeleton and the validation file

**Files:**

- Create: `scripts/cube_validation/__init__.py`, `__main__.py`, `config.py`
- Test: `tests/scripts/cube_validation/test_config.py`,
  `tests/scripts/cube_validation/__init__.py`

**Interfaces:**

- Produces: `load_view_config(path: Path) -> ViewConfig`; frozen dataclasses
  `ViewConfig`, `Comparison`,
  `RowSpec(grain: list[ColumnPair], values: list[ColumnPair])`, `Proof` fields
  as plain values, `Anchor`, `Identity`, `Decision`,
  `ColumnPair(dashboard: str, cube: str)`;
  `write_proof(path, comparison_id, proof_dict) -> None` (rewrites only that
  comparison's `proof:` key); `ConfigError(Exception)` whose message names the
  file and the key path.

- [ ] **Step 1: Confirm Cube ignores `src/cube/validation/`.** Query context7
      (`mcp__context7__query-docs`, library Cube) for the default `schemaPath`
      and confirm `src/cube/cube.js` sets none (it sets `driverFactory`,
      `checkAuth` and group hooks only). Expected: default `model`. If Cube
      Cloud loads anything outside `model/`, stop and report.
- [ ] **Step 2: Write failing tests.**

```python
def test_loads_example(tmp_path): ...  # the YAML above round-trips; comparisons[0].dims[0].cube == "regions_region_name"
def test_unknown_call_is_refused(tmp_path):  # call: maybe
    with pytest.raises(ConfigError, match=r"decisions\[0\]\.call"): ...
def test_probe_and_probe_sql_are_exclusive(tmp_path): ...  # ConfigError names comparisons[0]
def test_file_under_model_is_refused(tmp_path):  # path .../src/cube/model/x.yml
    with pytest.raises(ConfigError, match="src/cube/model"): ...
def test_fix_calls_need_a_task(tmp_path): ...  # call fix_cube with task "" -> ConfigError
```

- [ ] **Step 3: Run:**
      `cd W && uv run pytest tests/scripts/cube_validation/test_config.py -q`
      Expected: FAIL, module not found.
- [ ] **Step 4: Implement `config.py`** with `yaml.safe_load` and explicit
      validation (no schema library). `__main__.py` calls
      `cli.main(sys.argv[1:])` and exits with its return code (`cli.py` arrives
      in Task 12; stub `main` returning 2 until then).
- [ ] **Step 5: Run tests.** Expected: PASS.
- [ ] **Step 6: Commit** `feat(cube): validation file loader` with `Refs #6150`.

### Task 2: As-of SQL rewriting

**Files:**

- Create: `scripts/cube_validation/timetravel.py`
- Test: `tests/scripts/cube_validation/test_timetravel.py`, fixtures
  `fixtures/cube_compiled.sql`, `fixtures/view_union.sql`

**Interfaces:**

- Consumes: a catalog object with `table(dataset: str, name: str) -> TableInfo`
  and `view_sql_as_of(dataset, name, ts) -> str` (Task 3 implements it; tests
  use a fake).
- Produces:
  `TableInfo(kind: Literal["TABLE","VIEW","EXTERNAL"], view_sql: str | None)`;
  `as_of(sql: str, ts: datetime, catalog) -> AsOf` where
  `AsOf(sql: str, tables: frozenset[str], live: frozenset[str])`;
  `pin_clock(sql: str, ts: datetime) -> str`.

Rules, each proven on 2026-10-26:

- dbt view refs: `` `teamster-332318`.`ds`.`t` `` with optional `as alias`. Skip
  a ref inside a string literal (dbt `union_relations` writes
  `'''`teamster-332318.ds.t`'''`): regex
  ``(?<!')`teamster-332318`\.`(\w+)`\.`(\w+)`(\s+as\s+`?(\w+)`?)?``.
- Cube refs: `(FROM|JOIN)\s+(\w+)\.(\w+)\s+AS\s+`(\w+)`(Cube writes` FROM
  kipptaf_marts.fct_x AS `alias` ``).
- A TABLE becomes
  `` `teamster-332318.ds.t` AS alias FOR SYSTEM_TIME AS OF TIMESTAMP '<utc>' ``:
  the alias comes before `FOR SYSTEM_TIME`.
- A VIEW becomes `(<its SQL as of ts, rewritten recursively>) AS alias`; depth
  over 12 raises `ValueError`.
- An EXTERNAL table is left as is and added to `live`.
- `pin_clock` replaces `current_date(<tz>)`, `current_datetime(<tz>)` and
  `current_timestamp()` (any case, any whitespace) with
  `date(timestamp '<utc>', <tz>)`, `datetime(timestamp '<utc>', <tz>)` and
  `timestamp '<utc>'`; no-argument forms keep no zone argument.

- [ ] **Step 1: Write failing tests.**

```python
def test_cube_table_gets_alias_before_clause(): ...  # fixture cube_compiled.sql; output contains "AS `locations` FOR SYSTEM_TIME AS OF TIMESTAMP '2026-10-22 20:44:04+00:00'"
def test_view_is_inlined_recursively(): ...          # fake: dim_locations VIEW -> stg TABLE; result.tables == {"kipptaf_google_sheets.stg_x"}
def test_quoted_ref_is_left_alone(): ...             # fixture view_union.sql: the '''...''' literal is unchanged
def test_external_table_is_read_live(): ...          # result.live == {"ds.sheet"}, no FOR SYSTEM_TIME on it
def test_pin_clock_variants():
    assert pin_clock("current_date('America/New_York')", TS) == "date(timestamp '2026-10-22 19:00:00+00:00', 'America/New_York')"
    assert pin_clock("CURRENT_TIMESTAMP()", TS) == "timestamp '2026-10-22 19:00:00+00:00'"
def test_view_depth_limit(): ...                     # self-referencing fake view -> ValueError
```

`fixtures/cube_compiled.sql` is Cube's compiled SQL for `avg_daily_attendance`
by `grade_level` and `locations_abbreviation` with a Region filter (5 joins:
`fct_student_attendance_enrollment_daily`, `dim_student_enrollments`,
`dim_locations`, `dim_dates`, `dim_regions`; `?` parameters). Get it once with
`mcp__claude_ai_Cube__sql`. `fixtures/view_union.sql` is a hand-written view
body with 1 backticked table ref, 1 `union_relations`-style quoted ref, and 1
`current_date('America/New_York')`.

- [ ] **Step 2: Run**
      `uv run pytest tests/scripts/cube_validation/test_timetravel.py -q`.
      Expected: FAIL.
- [ ] **Step 3: Implement `as_of` and `pin_clock`.** `as_of` applies `pin_clock`
      to the outer SQL and every inlined view body.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(cube): rewrite SQL as of a moment`.

### Task 3: BigQuery access, view history and moments

**Files:**

- Create: `scripts/cube_validation/bq.py`, `scripts/cube_validation/moment.py`
- Test: `tests/scripts/cube_validation/test_bq.py`, `test_moment.py`

**Interfaces:**

- Consumes: `TableInfo` (Task 2).
- Produces:
  - `class Warehouse` (wraps `bigquery.Client(project="teamster-332318")`):
    `table(ds, name) -> TableInfo`, `view_sql_as_of(ds, name, ts) -> str`,
    `price(sql: str) -> float` (USD at $6.25 per TiB from a dry run),
    `rows(sql: str) -> list[dict]`, and a `budget(max_usd: float)` context
    manager that raises `CostCapError` once summed prices pass the cap.
  - `Build(start: datetime, end: datetime, job_id: str)`;
    `fact_builds(wh, fact: str, since: datetime) -> list[Build]` from
    `` `teamster-332318`.`region-us`.INFORMATION_SCHEMA.JOBS_BY_PROJECT ``
    (successful jobs whose `destination_table` is the fact, any statement type);
  - `pick_moment(builds, now, requested: datetime | None) -> Build` raising
    `MomentError`;
  - `fingerprint(wh, table: str, ts: datetime) -> int` using
    `bit_xor(farm_fingerprint(to_json_string(t)))`;
    `changed_between(wh, tables, t1, t2) -> list[str]`.

Behavior:

- `view_sql_as_of` returns today's `view_query` when the view's `modified` is at
  or before `ts`; otherwise the body of the latest successful `CREATE_VIEW` job
  for that view that started before `ts` (text after the first `as` that follows
  `OPTIONS(...)` or the view name). No such job: raise `ViewHistoryError` naming
  the view.
- `pick_moment`: with `requested`, the build whose `end` equals it or the latest
  build ending at or before it; refuse when that build's `start` is older than
  `now - 7 days + 1 hour`. Without `requested`, the latest build. No build:
  `MomentError("no successful build of <fact> in the last 7 days")`.

- [ ] **Step 1: Write failing tests** with a fake BigQuery client returning
      canned rows (no network).

```python
def test_view_sql_uses_current_when_unchanged(): ...
def test_view_sql_uses_create_view_job_when_changed_after(): ...   # Review Focus 1
def test_view_history_missing_is_refused(): ...                    # ViewHistoryError names the view
def test_pick_latest_build(): ...
def test_requested_moment_outside_window_is_refused():             # Review Focus 2
    with pytest.raises(MomentError, match="7 days"): ...
def test_budget_stops_past_cap(): ...                              # price 3 + 3 with cap 5 -> CostCapError
```

- [ ] **Step 2: Run**
      `uv run pytest tests/scripts/cube_validation/test_bq.py tests/scripts/cube_validation/test_moment.py -q`.
      Expected: FAIL.
- [ ] **Step 3: Implement `bq.py` and `moment.py`.**
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Live check (ADC, no fixture):**
      `cd W && uv run python -c "from scripts.cube_validation import bq, moment; ..."`
      listing builds of `kipptaf_marts.fct_student_attendance_enrollment_daily`
      since 2026-10-22. Expected: includes a build starting 2026-10-22 16:44 ET.
- [ ] **Step 6: Commit** `feat(cube): fact builds, view history and cost guard`.

### Task 4: Cube compiled SQL

**Files:**

- Create: `scripts/cube_validation/cube_client.py`
- Test: `tests/scripts/cube_validation/test_cube_client.py`

**Interfaces:**

- Produces:
  - `mint_token(secret: str, email: str, now: int, ttl: int = 300) -> str`:
    HS256 JWT, payload exactly `{"email", "iat", "exp"}`, base64url without
    padding.
  - `class Cube(base_url: str, secret: str, email: str, fetch=urlopen_json)`:
    `compiled(query: dict) -> Compiled` (GET `/sql?query=<json>`),
    `load(query: dict) -> list[dict]` (POST `/load`). Header
    `Authorization: <token>` with no `Bearer`. Base URL from `CUBE_REST_URL`
    (same variable `src/cube/mcp/server.py` reads; it includes
    `/cubejs-api/v1`).
  - `Compiled(sql: str, params: list, pre_aggregations: list)`;
    `bind(compiled) -> str` inlines `?` parameters as BigQuery literals (strings
    single-quoted with `\` and `'` escaped; numbers bare);
    `drop_limit(sql) -> str` removes a trailing `LIMIT <n>`.
  - `refuse_unless_safe(compiled, *, view_fact: str, network_schools: set[str]) -> None`
    raising `CubeRefusal` when `pre_aggregations` is non-empty, when the SQL
    reads a `kipptaf_marts.fct_*` other than `view_fact`, or when the bound
    school list (the `abbreviation IN (...)` parameters) is a strict subset of
    `network_schools`.
  - `network_schools(wh) -> set[str]`: the abbreviation set the `network` scope
    enumerates (read `src/cube/access.js` lines 151 to 161 for its source table
    and mirror that query).

- [ ] **Step 1: Write failing tests** (fake `fetch`).

```python
def test_token_payload_and_signature(): ...       # recompute hmac over header.payload; payload keys == {"email","iat","exp"}
def test_header_has_no_bearer(): ...
def test_bind_escapes_quotes():
    assert bind(Compiled("x = ?", ["O'Neil"], [])) == "x = 'O\\'Neil'"
def test_preaggregation_is_refused(): ...          # Review Focus 3
def test_second_fact_is_refused(): ...
def test_short_school_list_is_refused(): ...
```

- [ ] **Step 2: Run**
      `uv run pytest tests/scripts/cube_validation/test_cube_client.py -q`.
      Expected: FAIL.
- [ ] **Step 3: Implement.** Read the `/sql` response shape from Cube's docs
      (context7) and map `sql.sql` to `(sql, params)` and `sql.preAggregations`
      to `pre_aggregations`.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Live smoke** through a throwaway
      `tests/test_zz_cube_validation.py` that calls `Cube(...).compiled(...)`
      for `avg_daily_attendance` by `grade_level`:
      `uv run pytest tests/test_zz_cube_validation.py -s --tb=short`. Expected:
      SQL mentions `fct_student_attendance_enrollment_daily`, params include the
      school list. Delete the file after.
- [ ] **Step 6: Commit** `feat(cube): compiled SQL with safety refusals`.

### Task 5: Comparing rows and cells

**Files:**

- Create: `scripts/cube_validation/compare.py`
- Test: `tests/scripts/cube_validation/test_compare.py`

**Interfaces:**

- Consumes: `Comparison`, `ColumnPair` (Task 1).
- Produces:
  - `reconcile_sql(cube_rows_sql: str, dashboard_rows_sql: str, rows: RowSpec, group_by: list[str]) -> str`:
    1 BigQuery query that full-outer-joins both sides on the grain and returns
    only aggregates: per bucket (`match`, `value_differs`, `dashboard_only`,
    `cube_only`) and per `group_by` value, `n_rows` and `n_students`.
  - `Group(comparison_id: str, column: str, value: str, bucket: str, n_rows: int, n_students: int)`
    and
    `groups_from(comparison_id: str, result_rows: list[dict]) -> list[Group]`
    (buckets other than `match`).
  - `scope_filters(comparison) -> list[dict]`: Cube filters for each `scope`
    entry, listed in the result.
  - `cell_verdict(dashboard: float | None, cube: float | None, decimals: int) -> Literal["pass","differs","dashboard_only","cube_only"]`:
    compares after `round(x, decimals)`; `decimals` already counts a percent's
    fraction digits (Task 8).
  - `clauses_for(columns: list[str], sql: str) -> list[str]`: each `WHERE`,
    `QUALIFY`, `HAVING` or `JOIN ... ON` predicate in `sql` that names one of
    `columns`, trimmed to 1 line.

- [ ] **Step 1: Write failing tests.**

```python
def test_reconcile_sql_returns_aggregates_only(): ...   # no grain column in the outer SELECT
def test_cell_verdict_at_displayed_decimals():
    assert cell_verdict(0.9321, 0.9324, decimals=3) == "pass"      # both show 93.2%
    assert cell_verdict(0.9321, 0.9372, decimals=3) == "differs"   # 93.2% vs 93.7%
    assert cell_verdict(None, 0.93, decimals=3) == "cube_only"
def test_clauses_for_finds_the_filter():
    assert clauses_for(["assessment_type"], "select * from t where assessment_type != 'x' and y = 1") == ["assessment_type != 'x'"]
def test_scope_filter_from_comparison(): ...
```

- [ ] **Step 2: Run**
      `uv run pytest tests/scripts/cube_validation/test_compare.py -q`.
      Expected: FAIL.
- [ ] **Step 3: Implement.** Split predicates on top-level `AND` only.
- [ ] **Step 4: Run tests.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(cube): row and cell comparison`.

### Task 6: Recorded decisions

**Files:**

- Create: `scripts/cube_validation/decisions.py`
- Test: `tests/scripts/cube_validation/test_decisions.py`

**Interfaces:**

- Consumes: `Decision` (Task 1); `Group` (Task 5).
- Produces: `sql_fingerprint(sql: str) -> str` (sha256 of SQL with comments
  removed, whitespace collapsed, lower-cased outside string literals);
  `apply(decisions, groups, fingerprints: dict[str, str]) -> Applied` with
  `Applied(open: list[Group], quiet: list[tuple[Decision, Group]], reconfirm: list[Decision], no_longer_needed: list[Decision])`.

- [ ] **Step 1: Write failing tests.**

```python
def test_whitespace_and_comment_changes_keep_fingerprint(): ...   # Review Focus 5
def test_logic_change_changes_fingerprint(): ...
def test_matching_decision_quiets_group(): ...
def test_changed_sql_asks_to_reconfirm(): ...    # decision moves to reconfirm; its group stays open
def test_missing_group_marks_no_longer_needed(): ...
```

- [ ] **Step 2 to 4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `feat(cube): apply recorded decisions`.

### Task 7: Anchors, identities and the strongest check

**Files:**

- Create: `scripts/cube_validation/checks.py`
- Test: `tests/scripts/cube_validation/test_checks.py`

**Interfaces:**

- Consumes: `Anchor`, `Identity` (Task 1); `Cube`, `bind` (Task 4).
- Produces:
  - `Finding(kind: Literal["anchor","identity"], measure: str, detail: str, left: float, right: float, passed: bool)`.
  - `anchor_query(anchor, view: str) -> dict`: a Cube query for the anchor's
    measure, `date_range` and `filters`. Anchors run on current data (the figure
    is frozen at its date; no time travel).
  - `anchor_finding(anchor, cube_value: float) -> Finding`: always a triage item
    showing both values and the difference; no threshold.
  - `identity_queries(identity, cut: dict) -> tuple[dict, dict]` and
    `identity_finding(identity, left: float, right: float) -> Finding` (equal at
    9 decimals passes).
  - `strongest_check(measure: str, results) -> Literal["matches a dashboard","anchored to a source","consistent only","none"]`.
    "consistent only" and "none" are never reported as validated.

- [ ] **Step 1: Write failing tests.**

```python
def test_anchor_difference_is_always_triaged(): ...
def test_identity_passes_at_9_decimals(): ...
def test_strongest_check_order(): ...   # dashboard pass beats anchor; anchor beats identity
def test_consistent_only_is_not_validated(): ...
```

- [ ] **Step 2 to 4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `feat(cube): anchors and consistency checks`.

### Task 8: Proving a workbook formula

**Files:**

- Create: `scripts/cube_validation/tableau.py`
- Test: `tests/scripts/cube_validation/test_tableau.py`, fixture
  `fixtures/sheet_formats.twb` (a trimmed `.twb` with 1 worksheet and 2
  measures, no data)

**Interfaces:**

- Produces:
  - `drop_number_formats(twb_xml: str, measures: list[str]) -> str`: removes
    `default-format` on those measures' `column` elements and their
    `text-format` rules in worksheet `style`.
  - `displayed_decimals(format_string: str) -> int`: digits of the compared
    value, so a percent counts its fraction: `"p0.0%"` → 3, `"p0%"` → 2,
    `"n#,##0"` → 0, `"0.00"` → 2.
  - `class Tableau(server)`: `download_twb(luid) -> str` (no extract),
    `workbook_updated(luid) -> datetime`,
    `refresh_started(workbook_luid) -> datetime` (latest completed
    extract-refresh job's start, workbook or its published datasource),
    `publish_copy(workbook_luid, xml_edit) -> str` (copy luid in `TEMP-CB`,
    named `ZZ-VALIDATE <workbook name>`),
    `export(copy_luid, sheet, filters: dict) -> list[dict]` (REST CSV with `vf`
    filters).
  - `prove(comparison, exports, probe_values) -> Proof` where
    `Proof(fingerprint: str, cells: int, failures: list[str], proven_at: datetime)`;
    proven only when every exported value equals the probe at the displayed
    decimals.

Before editing any XML, invoke the `tableau-workbook-xml` skill. The probe runs
over the dashboard view rebuilt as of `refresh_started` (Task 2 and 3), so 1 SQL
dialect serves both the proof and later comparisons. Read the refresh start
before and after the exports; if it moved, discard the exports and retry once.
Parameter cuts are out of scope for automated proof (the Tableau MCP returns 400
on parameters here); the result lists them as "prove in the browser".

- [ ] **Step 1: Write failing tests** (offline; fake server object).

```python
def test_drop_number_formats_removes_only_named_measures(): ...
def test_displayed_decimals_cases(): ...
def test_prove_fails_on_one_mismatch(): ...
def test_refresh_moved_triggers_retry(): ...
```

- [ ] **Step 2 to 4:** run (FAIL), implement with `tableauserverclient`
      (`TableauServerResource` in `src/teamster/libraries/tableau/resources.py`
      shows sign-in; env vars `TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`,
      `TABLEAU_TOKEN_NAME`, `TABLEAU_PERSONAL_ACCESS_TOKEN`), run (PASS).
- [ ] **Step 5: Commit** `feat(cube): prove a workbook formula once`.

### Task 9: Finding comparisons

**Files:**

- Create: `scripts/cube_validation/discover.py`
- Test: `tests/scripts/cube_validation/test_discover.py`

**Interfaces:**

- Produces:
  - `tableau_exposures(path: Path) -> list[Exposure]` reading
    `src/dbt/kipptaf/models/exposures/tableau.yml`;
    `Exposure(name, label, luid, models: list[str])` with the luid at
    `config.meta.dagster.asset.metadata.id`.
  - `calculated_fields(twb_xml: str) -> list[Calc(caption, formula, worksheets)]`.
  - `rank(measure: str, member_sql: str, calcs) -> list[Candidate]`: score by
    shared tokens between the measure name, the columns in its SQL, and each
    calc's caption and formula; top 5 per workbook, score over 0.
- Writes nothing: `discover` prints candidates; the analyst confirms and the
  skill writes `comparisons:` entries with `confirmed: true`.

- [ ] **Step 1: Write failing tests.**

```python
def test_exposure_luid_path(): ...
def test_calculated_fields_from_twb(): ...
def test_rank_prefers_formula_on_shared_columns(): ...   # "is_present" calc outranks "Attendance Pts"
```

- [ ] **Step 2 to 4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `feat(cube): find candidate comparisons`.

### Task 10: Result and review issue

**Files:**

- Create: `scripts/cube_validation/report.py`
- Test: `tests/scripts/cube_validation/test_report.py`

**Interfaces:**

- Consumes: `Applied` (Task 6), findings (Task 7), cell and bucket results (Task
  5), `AsOf.live` (Task 2), changed dimensions (Task 3).
- Produces: `render_local(run) -> str` (Markdown to the terminal and
  `~/.cache/cube-validation/<view>/<moment>/result.md`), sections in the spec's
  order: each measure with strongest check and verdict; triage list; decisions
  applied, to re-confirm, no longer needed; sources read live; dimensions that
  changed between the moment's start and end; scopes applied; cost.
  `render_review_issue(domain: str, runs) -> str`: body in the
  `.github/ISSUE_TEMPLATE/feature_request.md` structure, domain-owner groups
  only, every count through `mask(n) -> str` (`"<10"` under 10).

- [ ] **Step 1: Write failing tests.**

```python
def test_mask_small_counts():
    assert mask(9) == "<10" and mask(10) == "10"
def test_review_issue_has_no_raw_small_counts(): ...
def test_local_result_lists_live_sources_and_changed_dims(): ...   # Review Focus 4
def test_consistent_only_measure_reads_not_validated(): ...
```

- [ ] **Step 2 to 4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Commit** `feat(cube): validation result and review issue`.

### Task 11: Command line

**Files:**

- Create: `scripts/cube_validation/cli.py` (replace the Task 1 stub)
- Test: `tests/scripts/cube_validation/test_cli.py`

**Interfaces:**

- Consumes: every module above.
- Produces `main(argv: list[str]) -> int` with commands:
  - `discover <view.yml> --measure <m>`: Task 9 candidates.
  - `prove <view.yml> --comparison <id>`: Task 8; writes `proof:` (fingerprint,
    cells, `proven_at`, the workbook's `updated_at`) into the file with
    `write_proof`.
  - `prove <view.yml> --check`: read-only sign-in; lists comparisons whose
    workbook `updated_at` is later than their proof's. `run` never signs in to
    Tableau; it prints each proof's date.
  - `check-api <view.yml>`: for the default cut and 2 more, `Cube.load` and the
    bound compiled SQL run now must agree at 9 decimals; refuse if the fact or a
    dimension rebuilt in between (`changed_between`).
  - `run <view.yml> [--moment <iso>] [--email <e>] [--max-usd 5]`: pick the
    moment; for each comparison and cut, dashboard rows as of `build.start`,
    Cube as of `build.end`; name the dimension tables in Cube's SQL that
    `changed_between` start and end; reconcile, cells, decisions, anchors,
    identities; render.
  - `review <view.yml>... --domain <name>`: prints the review-issue body. Never
    posts.
  - Return codes: 0 done, 1 refused (message says why), 2 usage error.

- [ ] **Step 1: Write failing tests** with fakes for `Warehouse`, `Cube`,
      `Tableau`.

```python
def test_run_uses_start_for_dashboard_and_end_for_cube(): ...
def test_run_refuses_comparison_without_proof(): ...    # exit 1, message names the comparison
def test_run_prices_before_running(): ...               # CostCapError -> exit 1 with dollars
def test_review_never_posts(): ...
```

- [ ] **Step 2 to 4:** run (FAIL), implement, run (PASS).
- [ ] **Step 5: Run the whole package's tests:**
      `uv run pytest tests/scripts/cube_validation -q`. Expected: all pass.
- [ ] **Step 6: Commit** `feat(cube): validation command line`.

### Task 12: Skill and the first validation file

**Files:**

- Create: `.claude/skills/cube-validation/SKILL.md`,
  `src/cube/validation/student_attendance_enrollment_daily_view.yml`

- [ ] **Step 1: Invoke `superpowers:writing-skills`**, then write the skill: a
      runbook for the analyst flow (list measures → `discover` → confirm →
      `prove` → `check-api` once per view → `run` → triage into the 4 calls →
      record decisions → `review` on the analyst's OK, posted by Claude with
      `mcp__github__issue_write`). Include the throwaway secrets runner from
      Global Constraints, the 7-day window, the 4 calls and where each goes, and
      the rule that the tool never posts to Slack. Description triggers:
      "validate Cube", "does Cube match the dashboard", `src/cube/validation/`.
- [ ] **Step 2: Write the attendance file** with 1 comparison (`ada-y1-region`
      as in the example above, `confirmed: true`, `proof: null`), 1 identity
      (`avg_daily_attendance` = `sum_attendance_value / sum_membership_value`),
      no anchors and no decisions yet. The analyst supplies the network-grant
      email; ask before committing it, since the file is committed.
- [ ] **Step 3: Load it:**
      `uv run python -c "from pathlib import Path; from scripts.cube_validation.config import load_view_config as l; print(l(Path('src/cube/validation/student_attendance_enrollment_daily_view.yml')).view)"`.
      Expected: `student_attendance_enrollment_daily_view`.
- [ ] **Step 4: Lint**
      `cd W && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-validation/SKILL.md src/cube/validation/student_attendance_enrollment_daily_view.yml </dev/null`.
      Expected: no lint findings (formatting is the hook's).
- [ ] **Step 5: Commit** `feat(cube): validation skill and attendance file`.

### Task 13: Live acceptance on the 2026-10-22 proof

Run before 2026-10-29 16:44 ET, when the 2026-10-22 16:44 build leaves the
time-travel window. After that, use the latest build and compare against a fresh
`prove`.

- [ ] **Step 1: `prove`** the `ada-y1-region` comparison through the throwaway
      runner. Expected: proof written, 0 failures, at least 1 cell per cut.
- [ ] **Step 2: `check-api`.** Expected: agree on all 3 cuts.
- [ ] **Step 3: `run --moment 2026-10-22T20:44:16Z`** (end of the 16:44 ET
      build; confirm the exact end from `fact_builds`). Expected: for Miami,
      Royalty grade 2 reads 0.932810551 on both sides and Courage grade 7 reads
      0.956382220 on both sides (Cube as of the build's end, dashboard rows as
      of its start), the same values the 2026-10-26 proof found.
- [ ] **Step 4: `run`** with the latest build. Expected: a result with strongest
      checks, a triage list, cost under $5, and no student-level row in the
      output.
- [ ] **Step 5: Delete** `tests/test_zz_cube_validation.py`; confirm
      `git -C W status --short` shows no throwaway file.
- [ ] **Step 6: File the builder and CI parts as their own issues**, linked from
      #6150, so they outlive this PR. Then push and open the PR from
      `.github/pull_request_template.md` with `Refs #6150`.
