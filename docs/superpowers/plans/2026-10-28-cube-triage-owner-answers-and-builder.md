# Cube triage, owner answers, and the builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add context-checked triage, owner answers in chat, and the Cube
builder's commands and runbooks to the validator in PR #6160.

**Architecture:** New logic goes in new modules beside the validator
(`triage.py`, `answers.py`, `builder.py`), because `pipeline.py` is already
1,895 lines; `pipeline.py` and `cli.py` only gain thin call sites. Every
judgment step (reading docs against a result, choosing tiers, sorting fields) is
a skill step; every deterministic step is a command with offline tests. The tool
still posts nothing: Claude posts what the analyst or owner approved.

**Tech Stack:** Python 3.12, PyYAML, `google-cloud-bigquery` through the
validator's `Warehouse`, Cube REST through `cube_client.Cube`, pytest with the
fakes in `tests/scripts/cube_validation/`.

**Spec:**
`docs/superpowers/specs/2026-10-28-cube-triage-owner-answers-and-builder-design.md`
(builds on
`docs/superpowers/specs/2026-10-26-cube-validation-and-build-skill-design.md`).

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-cube-validation-and-build-skill`.
  Run every command from it; `git -C <worktree>` for git.
- Tests: `uv run pytest tests/scripts/cube_validation -q` (never bare
  `uv run pytest`: the rest of `tests/` is live integration tests).
- Stage files by name; write each commit message to a file in the session
  scratchpad and `git commit -F <file>`. End every message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Refs #6150`
  (builder tasks: `Refs #6157`).
- The tool posts nothing and never calls GitHub or Asana. Claude posts only what
  the analyst or the owner approved.
- Nothing about one student or one staff member reaches GitHub, git, or a
  decision. A value prints only for a column in `report._SHOWN_COLUMNS`, and
  only for a group of `report.MASK_BELOW` (10) or more students; counts under 10
  print as `<10` (`report.mask`). Every other column is an identifier and fails
  closed (`report._is_identifier`).
- Every BigQuery query goes through `bq.Warehouse` (priced first, run cap, daily
  cap `--max-usd-per-day`, view cache). No new `bigquery.Client` use.
- Cube is reached over `https` only, except `http` to `localhost` or `127.0.0.1`
  (Task 10).
- Time travel reaches 7 days: a hand check pinned to a moment older than that
  cannot run.
- Docstrings and comments follow `.claude/rules/comments.md`: the constraint and
  the why, no measurements or history.
- `count_students` means the enrollment headcount only (#6176); the builder
  never proposes another meaning under that name.

## Review Focus

1. A triage value check on an identifier column (a student number captioned
   "ID", a name, an email) must neither compare nor print values; Task 4 pins it
   with `test_value_check_skips_identifier_and_high_cardinality_columns`.
2. An owner's answers comment edited by hand, malformed, or naming decision ids
   that changed since `review` must write nothing at all; Task 9 pins it with
   `test_record_answers_refuses_whole_comment_on_any_mismatch`.
3. An owner note with an email address or a long number must be refused before
   anything is written; Task 9 pins it with
   `test_record_answers_refuses_email_and_number_runs_in_notes`.
4. A run whose moment is more than 7 days old reaches `review`: the questions
   JSON must say the pinned checks have expired instead of offering SQL that
   fails; Task 7 pins it with `test_hand_checks_expire_after_7_days`.
5. A local Cube URL that only looks local (`http://localhost.evil.com`,
   `http://127.0.0.1@evil.com`) must be refused; Task 10 pins it with
   `test_http_allowed_only_for_loopback_hosts`.

---

## File Structure

- Create `scripts/cube_validation/triage.py`: evidence and suggested calls for
  open items (Part A).
- Create `scripts/cube_validation/answers.py`: example cells, pinned hand-check
  SQL, the review questions JSON, and parsing the owner's answers (Part B).
- Create `scripts/cube_validation/builder.py`: Cube member listing, duplicate
  check, workbook re-inventory, gap-catalog parsing and the 3-source inventory
  (Part C).
- Modify `cube_client.py` (meta, loopback http), `config.py` (`fix_source`,
  `tasks:`, filter notes, decision writer), `pipeline.py` (prove records filter
  notes; run saves hand-check material; review adds JSON), `report.py`
  (footnote, JSON block), `moment.py` and `cli.py` (dev-build dataset, new
  commands).
- Create `.claude/skills/cube-validation-answers/SKILL.md` (owner) and
  `.claude/skills/cube-builder/SKILL.md`; modify
  `.claude/skills/cube-validation/SKILL.md`.
- Tests: one new file per new module (`test_triage.py`, `test_answers.py`,
  `test_builder.py`) plus additions to existing test files.

## Execution order

The analyst tests the builder on DDI Suite's student tier buckets on 2026-10-29
at 1pm, so the builder goes first. Run the tasks in this order:

1. Task 1, then Tasks 11, 12, 13, 10.
2. Task 14 Step 3 (the `cube-builder` runbook) with its lint and its own commit
   (`docs(cube): builder runbook`, `Refs #6157`).
3. Tasks 2 to 9.
4. Task 14 Steps 1, 2 and 4 to 5 (the other 2 runbooks).

## Live checks

The controller runs these after the named task's review passes, never the
implementer. They run under a throwaway `tests/test_zz_*.py` in the main
checkout (the pytest fixture loads the Cube secret), pointed at this worktree's
package, and are deleted afterwards. A failure is a defect in that task.

- Task 11: `members` against Cube Cloud. Expect every public measure listed with
  compiled SQL, and 4 `count_students` from `same_name`. No BigQuery.
- Task 12: `inventory-workbook` on
  `/workspaces/teamster/.claude/scratch/ddi-twb/ddi_suite.twb`. Expect the
  Student Tier field as a cut or filter on many sheets, and parameters marked
  presentation.
- Task 13: `inventory` on the `ddi_suite` section of
  `docs/superpowers/plans/2026-10-02-cube-gap-catalog-assessments.md`, with Task
  12's output as the review and an empty Asana list. Expect a Student Tier row
  with no member.
- Task 10, Task 4 and Task 8 need a DDI validation file and a local Cube server;
  they run during or after the 2026-10-29 test, on the DDI branch's file, not in
  this run.

---

## Part A: context-checked triage

### Task 1: Cube member docs from `/meta`

**Files:**

- Modify: `scripts/cube_validation/cube_client.py` (class `Cube`)
- Test: `tests/scripts/cube_validation/test_cube_client.py`

**Interfaces:**

- Produces: `Cube.meta() -> dict` (GET `/meta`, raw JSON); `MemberDoc` frozen
  dataclass
  `(name: str, title: str, description: str, ai_context: str, kind: str)` with
  `kind` in `measure`, `dimension`, `segment`;
  `member_docs(meta: dict, view: str) -> dict[str, MemberDoc]` keyed by the bare
  member name (no `view.` prefix).

- [ ] **Step 1: Write the failing tests**

```python
def test_meta_calls_meta_endpoint():
    calls = []
    cube = Cube("https://c/cubejs-api/v1", "s", "e@x", fetch=lambda m, u, h, b: calls.append((m, u)) or {"cubes": []})
    assert cube.meta() == {"cubes": []}
    assert calls == [("GET", "https://c/cubejs-api/v1/meta")]


def test_member_docs_reads_description_and_ai_context_for_one_view():
    meta = {"cubes": [
        {"name": "v", "measures": [{"name": "v.pct_tardy", "title": "Pct Tardy", "description": "Share tardy.", "meta": {"ai_context": "Codes T*."}}],
         "dimensions": [{"name": "v.grade_level", "title": "Grade", "description": "Grade."}], "segments": []},
        {"name": "other", "measures": [{"name": "other.x"}], "dimensions": [], "segments": []},
    ]}
    docs = member_docs(meta, "v")
    assert set(docs) == {"pct_tardy", "grade_level"}
    assert docs["pct_tardy"].ai_context == "Codes T*."
    assert docs["grade_level"].ai_context == ""
    assert docs["grade_level"].kind == "dimension"
```

- [ ] **Step 2:** Run
      `uv run pytest tests/scripts/cube_validation/test_cube_client.py -q`.
      Expected: FAIL (`meta`, `member_docs` undefined).
- [ ] **Step 3:** Implement `Cube.meta` with `self._call("GET", "/meta")` and
      `member_docs`; missing `description` or `meta.ai_context` read as `""`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `cube_client.py` and its test:
      `feat(cube): read member docs from Cube meta`.

### Task 2: Prove records why a filter filters nothing

**Files:**

- Modify: `scripts/cube_validation/pipeline.py` (`SheetGaps`, `sheet_gaps`, the
  `prove` call that builds the proof dict)
- Modify: `scripts/cube_validation/config.py` (`Proof`, its loader)
- Test: `tests/scripts/cube_validation/test_sheet_shape.py` (or the file that
  tests `sheet_gaps` today), `tests/scripts/cube_validation/test_config.py`

**Interfaces:**

- Produces: `SheetGaps.notes: dict[str, str]` and
  `Proof.filter_notes: dict[str, str] | None` (caption to note),
  `SheetGaps.columns: dict[str, str]` and
  `Proof.missing_columns: dict[str, str] | None` (caption to the datasource
  column name, only for a plain column, never a calculation). The notes are
  exact strings: `copy of <mapped caption>` for a calculation whose whole
  formula is one reference to a field the comparison maps, and
  `display switch on <parameter caption>` for a calculation whose formula reads
  a `[Parameters].` field. `None` means the proof predates them, as for
  `missing_cuts`.

- [ ] **Step 1: Write the failing tests** against a fixture `.twb` built in the
      test (follow the existing `sheet_gaps` tests' fixture style): one filter
      on `[Grade Copy]` whose formula is `[grade_level]` with `grade_level`
      mapped, one on `[Show Rate]` whose formula reads `[Parameters].[Metric]`,
      one plain column `[enroll_status]` unmapped.

```python
def test_sheet_gaps_notes_copies_and_display_switches():
    gaps = sheet_gaps(TWB, comparison)
    assert gaps.notes == {"Grade Copy": "copy of Grade", "Show Rate": "display switch on Metric"}
    assert gaps.columns == {"Enroll Status": "enroll_status"}


def test_proof_loads_without_filter_notes_as_none(tmp_path):
    cfg = load_view_config(_write(tmp_path, proof_without_notes))
    assert cfg.comparisons[0].proof.filter_notes is None
    assert cfg.comparisons[0].proof.missing_columns is None
```

- [ ] **Step 2:** Run both test files. Expected: FAIL.
- [ ] **Step 3:** Extend `sheet_gaps` and `Proof`; `prove` writes `filter_notes`
      and `missing_columns` into the proof dict passed to `write_proof`. Use
      `finder.calculated_fields` for formulas.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit:
      `feat(cube): proofs record copies and display switches`.

### Task 3: Evidence and suggested calls

**Files:**

- Create: `scripts/cube_validation/triage.py`
- Test: `tests/scripts/cube_validation/test_triage.py`

**Interfaces:**

- Consumes: `MemberDoc`, `member_docs` (Task 1); `Proof.filter_notes`,
  `Proof.restricting_filters` (Task 2); `compare.Group`, `compare.Gap`,
  `compare.CellDiff`; `report.RunResult`; `config.ViewConfig`.
- Produces:
  - `SUGGESTIONS = ("map_filters", "filters_nothing", "docs", "owner")`, the
    order the analyst's batch shows them, owner last.
  - `Item` frozen dataclass
    `(id: str, kind: str, comparison: str, label: str, stub: dict)`: `kind` in
    `group`, `cells`, `gap`; `id` is stable across runs
    (`<comparison>:<column>=<value>` for a group, `<comparison>:cells`,
    `cut:<caption>` / `filter:<caption>` for a gap); `label` is the masked line
    `report` prints; `stub` is the decision's key fields (`comparison` +
    `group`, `comparison` + `cells: true`, or `missing_cut` / `missing_filter`).
  - `Suggestion` frozen dataclass
    `(item: Item, suggestion: str, evidence: tuple[str, ...], candidates: tuple[str, ...] = ())`.
  - `open_items(run: RunResult) -> list[Item]`.
  - `suggest(cfg: ViewConfig, run: RunResult, docs: dict[str, MemberDoc], values: Callable[[str, str], str] | None = None) -> list[Suggestion]`.
    `values(caption, member)` returns a value-check verdict (Task 4); `None`
    skips value checks.

Rules `suggest` applies, first match wins:

1. A filter gap with a note in any proof's `filter_notes`, or one not in any
   `restricting_filters`: `filters_nothing`; evidence is the note, or
   `keeps every member on <sheets>`.
2. A gap whose caption matches a member by name, title or description tokens
   (reuse `discover._tokens`): `candidates` lists them; with `values` given and
   a verdict starting `same values`, `map_filters`.
3. An item whose involved members (the measure, plus a group's columns) have a
   non-empty `description` or `ai_context`: `docs`; evidence quotes each as
   `<member>: <text>`.
4. Otherwise `owner`, evidence `no description or ai_context answers it`.

- [ ] **Step 1: Write the failing tests**, one per rule plus ordering:

```python
def test_unrestricting_filter_suggests_filters_nothing(): ...
    # gap filter "Enroll Status", restricting_filters=[] -> filters_nothing,
    # evidence ("keeps every member on Roster",)
def test_copy_note_suggests_filters_nothing(): ...
def test_caption_match_lists_candidates_without_value_check(): ...
    # values=None -> suggestion "owner" or "docs", candidates ("grade_level",)
def test_same_values_suggests_map_filters(): ...
def test_member_docs_suggest_docs_with_quoted_evidence(): ...
def test_nothing_found_goes_to_owner_last(): ...
    # [s.suggestion for s in result] sorted by SUGGESTIONS order
def test_item_ids_are_stable_and_hold_no_unreviewed_value(): ...
    # a group on an identifier column gets id "<comparison>:<column>=<redacted>"
```

- [ ] **Step 2:** Run
      `uv run pytest tests/scripts/cube_validation/test_triage.py -q`. Expected:
      FAIL (module missing).
- [ ] **Step 3:** Implement `triage.py`. Reuse `report._shown_value` and
      `report.mask` for labels so masking matches the review issue.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): suggest a call for each open item`.

### Task 4: Value checks and the `triage` command

**Files:**

- Modify: `scripts/cube_validation/triage.py`, `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_triage.py`,
  `tests/scripts/cube_validation/test_cli.py`

**Interfaces:**

- Consumes: Task 3; `Proof.missing_columns` (Task 2); `bq.Warehouse.rows`;
  `pipeline._priced_load`; `pipeline._as_of` for the dashboard side.
- Produces:
  - `REFERENCE_MAX_VALUES = 50`.
  - `value_check(wh: Warehouse, cube: Cube, cfg: ViewConfig, column: str, member: str, moment: Build, pii: set[str]) -> str`,
    returning exactly one of: `same values: map it under filters:`,
    `same field, different coding`, `different values`,
    `not compared: identifier column`. It compares distinct values of
    `<dashboard_view>.<column>` as of `moment.start` with the member's distinct
    values from Cube. It never compares when the member is in `pii` (members
    whose Cube meta carries `meta.contains_pii: true`, or whose name ends in
    `_number`, `_id`, `_name`, `_email`), or when either side has more than
    `REFERENCE_MAX_VALUES` values. It prints values only when the member is in
    `report._SHOWN_COLUMNS`; otherwise only the verdict.
  - `triage` subcommand: `triage <view.yml>` reads the latest `run.json` for the
    view (same lookup as `pipeline.review`, same refusal when decisions
    changed), calls `Cube.meta`, runs `suggest` with `value_check`, writes
    `triage.json` beside that `run.json`, and prints the items grouped by
    `SUGGESTIONS` order with their evidence. Takes `--max-usd` and
    `--max-usd-per-day` like `run`.
  - `triage.json`:
    `{"view", "moment", "decisions_fingerprint", "items": [{"id", "kind", "comparison", "label", "stub", "suggestion", "evidence", "candidates"}]}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_value_check_skips_identifier_and_high_cardinality_columns(): ...
    # member "student_number" -> "not compared: identifier column", no query run
    # 51 distinct values -> "not compared: identifier column", no values printed
def test_value_check_same_values_and_different_coding(): ...
    # {"A","B"} vs {"A","B"} -> "same values: map it under filters:"
    # {"W","B"} vs {"White","Black"} with a description match -> "same field, different coding"
def test_triage_command_writes_triage_json_beside_latest_run(fakes, tmp_path): ...
def test_triage_refuses_when_decisions_changed_since_run(fakes, tmp_path): ...
```

- [ ] **Step 2:** Run both files. Expected: FAIL.
- [ ] **Step 3:** Implement; the dashboard-side distinct query reads through
      `pipeline._as_of` and `wh.rows`, the Cube side through
      `pipeline._priced_load`, so both count against the caps.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): triage command with value checks`.

---

## Part B: owner answers in chat

### Task 5: `fix_source`, the `tasks:` block, and the footnote

**Files:**

- Modify: `scripts/cube_validation/config.py`,
  `scripts/cube_validation/report.py`
- Test: `tests/scripts/cube_validation/test_config.py`,
  `tests/scripts/cube_validation/test_report.py`

**Interfaces:**

- Produces: `CALLS` gains `fix_source`;
  `CALLS_NEEDING_TASK = ("fix_dashboard", "fix_cube", "fix_source")`;
  `ViewConfig.tasks: dict[str, str]` from an optional top-level `tasks:` with
  keys `cube_fix` and `dashboard_fix` only, each value passing the existing
  `_TASK` pattern. The review footnote reads `Counts under 10 show as \`<10\`,
  and identifiers of students and staff are hidden.`

- [ ] **Step 1: Write the failing tests**

```python
def test_fix_source_needs_a_task(tmp_path): ...       # ConfigError mentions "task"
def test_tasks_block_accepts_only_known_keys(tmp_path): ...  # "other_fix" -> ConfigError
def test_tasks_block_values_must_be_links(tmp_path): ...     # "see Asana" -> ConfigError
def test_review_footnote_names_students_and_staff(): ...
```

- [ ] **Step 2:** Run both files. Expected: FAIL.
- [ ] **Step 3:** Implement. A `fix_source` decision stays quiet like every
      other call, and the measure's verdict still reads cells only, so it never
      reads `validated` while a cell differs; no other change.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): fix_source call and a tasks block`.

### Task 6: `run` saves what the hand checks need

**Files:**

- Modify: `scripts/cube_validation/pipeline.py` (`Cell`, `_compare_one`, `run`,
  `_run_from_json`), `scripts/cube_validation/report.py` (`RunResult`),
  `scripts/cube_validation/bq.py` (`Warehouse.estimate`)
- Test: `tests/scripts/cube_validation/test_cli.py` (run tests use the fakes),
  `tests/scripts/cube_validation/test_bq.py`

**Interfaces:**

- Produces on `RunResult` (all default empty, so older `run.json` files still
  load):
  - `diff_cells: list[dict]`: every cell whose verdict is not `pass` or
    `dashboard_filtered`, as
    `{"comparison", "cut", "key", "dims", "dashboard", "cube", "n_students"}`.
    `dims` are Cube member names and values; `n_students` is `None` unless
    counted below.
  - `cell_sql: dict[str, dict[str, list[str]]]`: per comparison, per cut label,
    `[dashboard_sql, cube_sql]`, both already expanded as of the moment (the
    `dash_at.sql` and the wrapped `cube_at.sql` the run executed).
  - `cell_sql_usd: dict[str, dict[str, list[float]]]`, the same shape: each
    side's dry-run price, for the owner, who runs it outside the caps.
  - `Warehouse.estimate(sql: str) -> float` in `bq.py`: the dry-run price, never
    recorded against the run or daily cap (`price` records; this must not).
- For a comparison with `rows`, one extra query per comparison counts each
  differing cell's students: `COUNT(DISTINCT <first grain dashboard column>)`
  over the as-of dashboard rows SQL, grouped by the comparison's dim dashboard
  columns. Comparisons without `rows` leave `n_students` as `None`.

- [ ] **Step 1: Write the failing tests**

```python
def test_run_saves_differing_cells_and_their_pinned_sql(fakes, tmp_path): ...
    # run.json["diff_cells"][0]["n_students"] == 12; cell_sql has both sides
    # and both contain "FOR SYSTEM_TIME AS OF"
def test_run_without_rows_leaves_n_students_none(fakes, tmp_path): ...
def test_estimate_does_not_count_against_the_daily_cap(tmp_path): ...
    # spent_today() unchanged after estimate()
def test_old_run_json_without_new_fields_still_loads(tmp_path): ...
```

- [ ] **Step 2:** Run
      `uv run pytest tests/scripts/cube_validation/test_cli.py -q`. Expected:
      FAIL.
- [ ] **Step 3:** Implement. The student count goes through `wh.rows`, so it is
      priced and capped.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit:
      `feat(cube): runs keep differing cells for hand checks`.

### Task 7: Example cell and pinned hand checks

**Files:**

- Create: `scripts/cube_validation/answers.py`
- Test: `tests/scripts/cube_validation/test_answers.py`

**Interfaces:**

- Consumes: `RunResult.diff_cells`, `RunResult.cell_sql`, `RunResult.moment`
  (Task 6); `report._is_identifier`, `report.MASK_BELOW`.
- Produces:
  - `TIME_TRAVEL_DAYS = 7`.
  - `HandCheck` frozen dataclass
    `(comparison: str, cut: str, dims: tuple[tuple[str, str], ...], dashboard: float | None, cube: float | None, dashboard_sql: str, cube_sql: str, dashboard_usd: float, cube_usd: float, expires: datetime, expired: bool)`;
    the prices come from `RunResult.cell_sql_usd` and show beside each SQL
    block.
  - `example_cell(run: RunResult, comparison: str) -> dict | None`: the
    differing cell with the largest `abs(dashboard - cube)` whose every dim
    passes `not report._is_identifier(column)` and whose `n_students` is at
    least `report.MASK_BELOW`; ties go to the lowest `key`. `None` when no cell
    qualifies.
  - `hand_check(run: RunResult, comparison: str, now: datetime) -> HandCheck | None`:
    wraps each side's saved SQL as
    `SELECT * FROM (<sql>) WHERE <dim> = <literal> AND ...` for the example
    cell, using `cube_client._literal`;
    `expires = run.moment.start + timedelta(days=TIME_TRAVEL_DAYS)`;
    `expired = now >= expires`.

- [ ] **Step 1: Write the failing tests**

```python
def test_example_cell_is_biggest_difference_with_reviewed_dims_only(): ...
def test_example_cell_skips_cells_under_10_students(): ...
def test_example_cell_skips_a_teacher_or_student_dim(): ...
    # dims (("teacher_name", "x"),) -> None
def test_no_example_cell_returns_none(): ...
def test_hand_check_sql_filters_to_the_example_cell(): ...
    # both SQL strings end with "WHERE regions_region_name = 'Newark' AND grade_level = '7'"
def test_hand_checks_expire_after_7_days(): ...
```

- [ ] **Step 2:** Run
      `uv run pytest tests/scripts/cube_validation/test_answers.py -q`.
      Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit:
      `feat(cube): pick an example cell and pin hand checks`.

### Task 8: Review questions as JSON in the issue

**Files:**

- Modify: `scripts/cube_validation/answers.py`,
  `scripts/cube_validation/report.py` (`render_review_issue`),
  `scripts/cube_validation/pipeline.py` (`review`)
- Test: `tests/scripts/cube_validation/test_answers.py`,
  `tests/scripts/cube_validation/test_report.py`

**Interfaces:**

- Consumes: the `questions` dict `render_review_issue` already builds (one per
  reason and task); Task 7; `triage.json` (Task 4) when present beside the run.
- Produces:
  - `questions_json(runs: list[RunResult], configs: list[ViewConfig], definitions: dict, triage: dict[str, dict], now: datetime) -> list[dict]`,
    one entry per question in the issue's order:
    `{"id": "Q<n>", "reason", "decisions": [<decision ids>], "views", "definitions": {"dashboard", "cube"}, "evidence": [<triage evidence for its items>], "counts": [<masked lines exactly as the markdown shows>], "hand_checks": [<HandCheck as dict, or {"comparison", "none": "no group cell with 10+ students differs; find an example under your own access"}>], "moment", "expires", "expired"}`.
  - The issue body ends with
    `<details><summary>Questions for Claude (JSON)</summary>` and a fenced
    `json` block of that list. Its strings come from the same masked text as the
    markdown; it holds no value the markdown hides.
  - Each hand check's SQL also appears in the markdown inside its own
    `<details>` block.

- [ ] **Step 1: Write the failing tests**

```python
def test_questions_json_matches_markdown_questions_one_to_one(): ...
def test_questions_json_hides_what_the_markdown_hides(): ...
    # a redacted value and a <10 count never appear unmasked in the JSON text
def test_question_without_example_cell_says_find_one_locally(): ...
def test_review_issue_ends_with_fenced_json_in_details(): ...
```

- [ ] **Step 2:** Run both files. Expected: FAIL.
- [ ] **Step 3:** Implement. `pipeline.review` passes `now` and the triage file,
      and stays offline.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): review issue carries questions as JSON`.

### Task 9: The decision writer, `add-decisions` and `record-answers`

**Files:**

- Modify: `scripts/cube_validation/config.py`,
  `scripts/cube_validation/answers.py`, `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_config.py`,
  `tests/scripts/cube_validation/test_answers.py`,
  `tests/scripts/cube_validation/test_cli.py`

**Interfaces:**

- Produces:
  - `config.write_decision(path: Path, decision: dict) -> None`: line-based like
    `write_proof`; replaces the `decisions:` item with the same `id`, or appends
    one. Re-loads the file afterwards and raises `ConfigError` (restoring the
    original text) if it no longer loads.
  - `add-decisions <view.yml> <approved.json>`: `approved.json` is a list of
    `{"id", "call", "reason", "task", "item": <triage item id>}`; each item's
    `stub` comes from the latest `triage.json`, fingerprints from the latest
    `run.json` the way step 9 of the `cube-validation` skill fills them today.
    Refuses an unknown item id.
  - `Answer` frozen dataclass
    `(question: str, decisions: tuple[str, ...], call: str, note: str, task: str = "")`.
  - `parse_answers(body: str) -> list[Answer]`: reads the one fenced `json`
    block in an answers comment; refuses zero or several blocks, a call outside
    `config.CALLS`, or `fix_source` without a task.
  - `NOTE_REFUSALS`: an email address (`\S+@\S+\.\w+`) or a run of 5 or more
    digits (`report._SEPARATED_DIGITS` or `\d{5,}`) in a note.
  - `record-answers <view.yml>... --comment <file> --author <login> [--yes]`:
    `<file>` is the comment body the skill saved. It prints the author and every
    change it would make, and writes only with `--yes`. For each answer: every
    listed decision id must exist in the given files with call `domain_owner`,
    else the whole comment is refused. The new reason is
    `<old reason> Owner: <note>`; the task is `tasks.cube_fix` for `fix_cube`,
    `tasks.dashboard_fix` for `fix_dashboard`, the answer's `task` for
    `fix_source`, and unchanged otherwise; a missing `tasks:` key refuses that
    answer. A free-text answer keeps `domain_owner`.

- [ ] **Step 1: Write the failing tests**

```python
def test_write_decision_replaces_by_id_and_keeps_comments(tmp_path): ...
def test_write_decision_restores_file_when_result_does_not_load(tmp_path): ...
def test_add_decisions_takes_stub_from_triage_and_fingerprints_from_run(fakes, tmp_path): ...
def test_record_answers_dry_run_prints_author_and_changes_writes_nothing(tmp_path, capsys): ...
def test_record_answers_maps_calls_to_tasks_block(tmp_path): ...
def test_record_answers_refuses_whole_comment_on_any_mismatch(tmp_path): ...
    # one unknown decision id -> nothing written to any file
def test_record_answers_refuses_email_and_number_runs_in_notes(tmp_path): ...
```

- [ ] **Step 2:** Run the 3 files. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit:
      `feat(cube): write decisions from triage and owner answers`.

---

## Part C: the builder

### Task 10: Local Cube and a dev build's moment

**Files:**

- Modify: `scripts/cube_validation/cube_client.py`,
  `scripts/cube_validation/moment.py`, `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_cube_client.py`,
  `tests/scripts/cube_validation/test_moment.py`,
  `tests/scripts/cube_validation/test_cli.py`

**Interfaces:**

- Produces:
  - `Cube.__init__` accepts `http` only when `urllib.parse.urlparse(url)` has
    `hostname` in `{"localhost", "127.0.0.1"}` and no `username`; everything
    else stays https-only.
  - `--fact-dataset <dataset>` on `run`, `check-api`, `prove` and `triage`: the
    dataset `moment.fact_builds` searches and `refuse_unless_safe` expects.
    Allowed: `kipptaf_marts` (default) or `zz_[a-z0-9]+_kipptaf_marts`; anything
    else is refused before any query.
  - `render_local` prints `Cube: <base URL host>` and `Fact: <dataset>.<fact>`
    so a PR description can say what was proven against what.

- [ ] **Step 1: Write the failing tests**

```python
def test_http_allowed_only_for_loopback_hosts():
    Cube("http://localhost:4000/cubejs-api/v1", "s", "e@x")
    Cube("http://127.0.0.1:4000/cubejs-api/v1", "s", "e@x")
    for bad in ("http://localhost.evil.com/x", "http://127.0.0.1@evil.com/x", "http://cube.example.com/x"):
        with pytest.raises(CubeError):
            Cube(bad, "s", "e@x")
def test_fact_builds_reads_a_dev_dataset(): ...
def test_fact_dataset_outside_allowed_names_is_refused(fakes, tmp_path): ...
def test_run_output_names_cube_host_and_fact(fakes, tmp_path, capsys): ...
```

- [ ] **Step 2:** Run the 3 files. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit:
      `feat(cube): validate against a local Cube and a dev build`
      (`Refs #6157`).

### Task 11: Cube members and the duplicate check

**Files:**

- Create: `scripts/cube_validation/builder.py`
- Modify: `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_builder.py`

**Interfaces:**

- Consumes: `Cube.meta` (Task 1), `Cube.compiled`, `cube_client.bind`,
  `cube_client._FACT`, `decisions.sql_fingerprint`.
- Produces:
  - `Member` frozen dataclass
    `(name: str, cube: str, kind: str, title: str, description: str, sql: str, sql_fingerprint: str, fact: str)`;
    `sql` is the measure's compiled expression (`pipeline._measure_expression`),
    `fact` the `fct_*` table it reads, `""` when none.
  - `members(cube: Cube) -> list[Member]`: every measure of every cube and view
    in `/meta`, each compiled alone. Compiling is free (no BigQuery).
  - `same_sql(found: list[Member]) -> list[list[Member]]`: groups with equal
    `sql_fingerprint` across different cubes, views excluded (a view member
    repeats its cube's).
  - `same_name(found: list[Member], name: str) -> list[Member]`: every member
    named `name` on any cube.
  - `members` subcommand writes `members.json` under the cache root and prints
    the `same_sql` groups.

- [ ] **Step 1: Write the failing tests** with a fake `Cube` returning a small
      `/meta` and compiled SQL:

```python
def test_members_compiles_every_measure_once(): ...
def test_same_sql_groups_equal_expressions_across_cubes(): ...
def test_same_sql_ignores_a_view_repeating_its_cube(): ...
def test_same_name_finds_count_students_on_every_cube(): ...
    # 4 cubes -> 4 members, each with its own fact and sql
```

- [ ] **Step 2:** Run
      `uv run pytest tests/scripts/cube_validation/test_builder.py -q`.
      Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): list Cube members and find duplicates`
      (`Refs #6157`).

### Task 12: Workbook re-inventory

**Files:**

- Modify: `scripts/cube_validation/builder.py`, `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_builder.py` (fixtures:
  `fixtures/calcs.twb`, `fixtures/roster.twb`)

**Interfaces:**

- Consumes: `discover.calculated_fields`, `discover.bins`,
  `discover.explain_bins`, `discover.aggregated_fields`, `discover.sheet_shape`,
  `discover.worksheet`, `discover.sheet_fields`.
- Produces:
  - `FieldUse` frozen dataclass
    `(caption: str, name: str, role: str, formula: str, sheets: tuple[str, ...], presentation: bool)`;
    `role` in `measure`, `cut`, `filter`, `parameter`; `formula` has code groups
    expanded (`explain_bins`); `presentation` is true for parameters, fields
    whose formula builds a URL (`http`), and fields built on the viewer's
    identity (`USERNAME()`, `ISMEMBEROF(`, the `personal` set from
    `sheet_fields`).
  - `workbook_inventory(twb_xml: str) -> list[FieldUse]`, one entry per field
    across every worksheet, sheets merged.
  - `inventory-workbook <twb path>` subcommand prints JSON. It reads a local
    file only; the skill downloads the workbook.

- [ ] **Step 1: Write the failing tests**

```python
def test_inventory_lists_each_field_once_with_all_its_sheets(): ...
def test_inventory_expands_code_groups_in_formulas(): ...
def test_inventory_marks_parameters_urls_and_identity_fields_presentation(): ...
```

- [ ] **Step 2:** Run `test_builder.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run it. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): re-inventory a workbook from its XML`
      (`Refs #6157`).

### Task 13: The 3-source inventory

**Files:**

- Modify: `scripts/cube_validation/builder.py`, `scripts/cube_validation/cli.py`
- Test: `tests/scripts/cube_validation/test_builder.py`

**Interfaces:**

- Consumes: Tasks 11 and 12.
- Produces:
  - `catalog_rows(markdown: str, slug: str) -> list[dict]`: from the section
    headed `## <Dashboard> (\`<slug>\`)`, the `### Measures`and`###
    Dimensions`tables, as`{"field", "kind", "status",
    "where"}`; `field`is the first column,`kind`is`measure`or`dimension`, `status`and`where`
    the columns with those headers.
  - `InventoryRow` frozen dataclass
    `(field: str, kind: str, member: str, sources: tuple[str, ...], disagreement: str)`;
    `sources` from `catalog`, `review`, `asana`; `member` is the Cube member
    matched by name or title, `""` when missing; `disagreement` names what
    differs (`catalog says cube-covered, no member found`, `only in asana`,
    ...), `""` when the sources agree.
  - `inventory(catalog: list[dict], review: list[FieldUse], asana: list[dict], found: list[Member]) -> list[InventoryRow]`;
    `asana` is a list of `{"field", "status"}` the skill writes from the
    dashboard's Asana task (retired items left out by the skill, deferred ones
    with status `deferred`).
  - `inventory <catalog.md> <slug> --review <json> --asana <json>` prints the
    rows as a markdown table for the build issue, then JSON. Presentation fields
    are left out.

- [ ] **Step 1: Write the failing tests**

```python
def test_catalog_rows_reads_the_dashboards_measures_and_dimensions(): ...
    # a 2-dashboard markdown string; only the slug's rows come back
def test_inventory_matches_members_and_flags_disagreements(): ...
def test_inventory_leaves_out_presentation_fields(): ...
def test_inventory_lists_deferred_asana_items_without_planning_them(): ...
```

- [ ] **Step 2:** Run `test_builder.py`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the full suite. Expected: PASS.
- [ ] **Step 5:** Commit: `feat(cube): inventory a dashboard from 3 sources`
      (`Refs #6157`).

---

## Part D: the runbooks

### Task 14: Skills

**Files:**

- Modify: `.claude/skills/cube-validation/SKILL.md`
- Create: `.claude/skills/cube-validation-answers/SKILL.md`
- Create: `.claude/skills/cube-builder/SKILL.md`
- Modify: `scripts/CLAUDE.md` (the `cube_validation/` row: new commands)

Read `.claude/rules/claude-md-editing.md` and `superpowers:writing-skills`
first. Each line must change a decision Claude makes; no history or counts.

- [ ] **Step 1: `cube-validation`**: after `run`, a triage step: run `triage`;
      search open GitHub issues for known gaps; check each `docs` item's quoted
      text against the result for contradictions; draft a reason per suggested
      close; show the analyst one batch grouped by suggestion, owner pile last;
      on "approve all" or "approve all but N", write `approved.json` and run
      `add-decisions`, then `run` again. Then `review` as today, plus: the issue
      is titled "Validate <dashboard> in Cube" and is the validation hub; after
      posting, fill `task` with it. Pick-up step: on "pick up the answers on
      #N", read only the comment the analyst names, save its body, show its
      author, check notes for a student's or staff member's name, then
      `record-answers --author <login>` without `--yes`, confirm with the
      analyst, rerun with `--yes`, then `run`. Document `fix_source`, the
      `tasks:` block, `--fact-dataset`, and the footnote.
- [ ] **Step 2: `cube-validation-answers`** (the owner's skill). Trigger phrases
      in plain words ("answer the attendance review", "walk me through issue
      #N"). Steps: read the validation issue's JSON block (never the markdown);
      say how many questions; warn when `expired` or within 1 day of `expires`;
      ask one question at a time with everything up front in the design's order
      (policy question, both definitions, who differs, what triage found, his
      checks with the collapsed SQL, the 5 choices plus free text); answer
      follow-ups from the same evidence and ask again; example students he asks
      for come from his own BigQuery access and stay in chat; for "the source
      data is wrong", draft the `fix_source` issue (question, definitions,
      counts, his note, what his session found, no student or staff detail), he
      picks the assignee and confirms, then it is opened; at the end, show the
      summary, check his notes for names, emails or numbers, and on his
      confirmation post 1 comment: a readable summary plus one fenced `json`
      block in `parse_answers`' shape.
- [ ] **Step 3: `cube-builder`**. Steps: inventory (`members`,
      `inventory-workbook`, an independent reviewer subagent that re-inventories
      the workbook XML without the catalog, the Asana task read into
      `asana.json`, then `inventory`); the duplicate rule (every cube searched;
      same SQL refused; a same-named member gets one of 3 verdicts the analyst
      confirms: reuse, add its cube to the view, or a new measure whose name
      says which students); the 5 tiers, shallowest first; the build issue holds
      inventory, disagreements and plan; Asana edits only for misses, shown in
      the issue first and made after approval; 3 PR types (YAML only; Cube adds
      or changes, analytics engineer review; fact adds or changes, data engineer
      review, merged before the type 2 that reads it); prove every PR before
      merge against a local Cube (`CUBEJS_SCHEMA_PATH` copy per
      `.claude/rules/cube-authoring.md`) by default, Cube Cloud Dev Mode by
      flag, `--fact-dataset zz_<user>_kipptaf_marts` for type 3; the PR
      description names the moment, the Cube host and the fact the run printed;
      when every tier is done, open the dashboard's validation issue and run the
      whole dashboard through triage and owner answers, then move its Asana
      stage subtasks from "Built in Cube" toward "Matches within tolerance".
- [ ] **Step 4:** Run
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-validation/SKILL.md .claude/skills/cube-validation-answers/SKILL.md .claude/skills/cube-builder/SKILL.md scripts/CLAUDE.md docs/superpowers/plans/2026-10-28-cube-triage-owner-answers-and-builder.md </dev/null`.
      Expected: no lint findings (formatting is the commit hook's).
- [ ] **Step 5:** Commit:
      `docs(cube): runbooks for triage, owner answers and the builder`
      (`Refs #6150`, `Refs #6157`).

---

## After the last task

- Run `uv run pytest tests/scripts/cube_validation -q`; all pass.
- Update the #6160 description: the new commands, the 2 new skills, the footnote
  change, and that the DDI Suite build is the builder's first real test, outside
  this PR.

## Rulings made while planning

- `triage` is its own command after `run`, not part of `run`, so a re-run does
  not pay for Cube meta calls and value checks every time.
- A "reference column" for value checks is one that is not PII-tagged, not named
  like an identifier, and has at most 50 values on both sides; values print only
  for the review's shown columns.
- `record-answers` refuses emails and digit runs in notes. A name cannot be
  detected reliably by code, so both skills check for names before anything is
  posted or written.
- `fix_source` stays quiet like every other call; the tool does not read GitHub,
  so "while its issue is open" is the analyst's re-run after it closes, not a
  check the tool makes.
- Hand checks are built from SQL the run already executed, so `review` stays
  offline and free; only the per-cell student count is a new query.
