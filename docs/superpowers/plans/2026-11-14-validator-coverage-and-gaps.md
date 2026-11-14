# Validator: Coverage and Known Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the validator's unused steps (`check-api`, anchors and identities,
cell sizing, `prove --check`), close differing cells by coverage with a
formula-difference outcome, give `run` its own pre-spend checks, a comparison
subset, progress lines and per-comparison latest results, close #6346, #6343 and
#6181 items 1, 7, 8, 12 and 14, rename the commands and keys, and update the
skills.

**Architecture:** Removals first, so new code is written against what stays. A
row group carries its per-cut row counts on each side (`Group.cut_rows`), and a
new `coverage.py` places each group's rows in a cell exactly: a cell closes when
every group with a row in it is in `cause` or decided, and a differing cell no
group has a row in becomes a formula difference (`<id>:formula`, decided with
`formula: true`). `run` (renamed `compare`) plans every comparison's queries,
checks the workbook and prices them all before the first billed query, then
compares the chosen comparisons and writes each one's result to
`<cache>/<view>/latest/<id>.json`; `run.json` is composed from those results,
each at its own moment. Old command and key names are refused with the new name.

**Tech Stack:** Python 3.13 via `uv run`, `google-cloud-bigquery`,
`tableauserverclient`, sqlglot, pytest with DuckDB (`--with duckdb`).

**Spec:**
`docs/superpowers/specs/2026-11-14-validator-coverage-and-gaps-design.md` (the
authority). Context:
`docs/superpowers/specs/2026-11-13-validator-saved-rows-resume-design.md` and
its plan (Tasks 1-12 done; its Task 13 is superseded). Issues #6410 (main),
#6346, #6343, #6181. PR #6402.

Worktree:
`/workspaces/teamster/.claude/worktrees/cristinabaldor/fix/claude-validator-second-fact-time-dims`
(`W` below). Package: `W/scripts/cube_validation/` (`P`). Tests:
`W/tests/scripts/cube_validation/` (`T`). Run every test from `W`:

```bash
uv run --with duckdb pytest tests/scripts/cube_validation/<file>::<test> -q
```

Baseline before Task 1:
`uv run --with duckdb pytest tests/scripts/cube_validation/ -q` → **1198
passed**. Every task ends with the whole suite green (the count moves as tests
are deleted and added; no failures, no new skips).

## Global Constraints

- One PR, #6402. Offline tests only; the implementer runs no warehouse, Cube or
  Tableau command. Live use goes through the `cube-validation` skill's runner,
  each spend approved by the owner.
- No parallel workers in `run` (`compare`) or `triage` (`sort`): one comparison
  and one explanation at a time. The new up-front price dry-runs one query at a
  time too.
- No student or staff value in any output a task adds that can reach GitHub: the
  formula item, progress lines, the trace's model chain, the #6346 labels.
  Counts under 10 are masked with `report.mask` / `report.shown_counts` wherever
  the text is posted (`evidence_posted`, review issue, decision YAML).
- Correctness over speed: never cut or loosen a check, guard or refusal to make
  a step faster.
- Coverage closes a cell only on proven or decided rows; a cell with an unproven
  row stays in `investigate`. A formula difference never closes without the
  owner seeing it (it is its own item and decision).
- An old validation file is refused, never silently read: `anchors:`,
  `identities:`, `rows.cell`, a `cells:` decision, and every key renamed in Task
  12, each with a message naming the key and what to do.
- Old command and key names are refused with the new name; no aliases.
- Docstrings follow `W/src/teamster/CLAUDE.md`; comments follow
  `.claude/rules/comments.md` (no measurements, no history).
- Commits: stage each file by name (never `-A`, `-u` or `.`), conventional
  commit subject, body `Refs #6410` (Task 9: `Refs #6346`; Task 11:
  `Refs #6343`; Tasks 10 and 13 add `Refs #6181`), last line
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Write the message
  to `<session scratchpad>/commit-msg-<slug>.txt` and `git commit -F` it if a
  hook blocks `-m`.
- Markdown edits (Task 14) are linted with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from `W`.

## Review Focus

1. A differing cell whose dim is part of the row grain (or whose comparison has
   no `rows`): groups cannot be placed in it, so it must stay open with a
   reason, never cover or read as a formula difference. Pinned in Task 5
   (`test_a_cell_on_a_grain_dim_stays_open_and_says_why`) and Task 6
   (`test_an_unplaceable_cell_is_never_a_formula_difference`).
2. A group whose rows sit in the same dims under another cut only: it has no row
   in this cut's cell, so it neither covers the cell nor keeps it from being a
   formula difference. Pinned in Task 5
   (`test_a_group_with_no_rows_under_the_cell_cut_does_not_cover_it`).
3. A composed `run.json` whose comparisons ran at different moments: an
   explanation, a trace or a hand check must read each comparison's own saved
   table and moment, never the newest. Pinned in Task 8
   (`test_an_explanation_reads_its_own_comparison_s_moment`).
4. A stale check that flags changed data, or misses a Cube or dbt view
   definition change. Expected: SQL or entry changes are stale, a new build
   alone is not. Pinned in Task 8 (`test_a_new_build_alone_is_not_stale`,
   `test_a_changed_view_definition_is_stale`).
5. A `formula: true` decision after a cell gains an unproven row: that cell
   leaves the formula item for the cells item; the decision keeps covering the
   rest. Pinned in Task 6
   (`test_a_cell_that_gains_a_row_leaves_the_formula_claim`).

---

## Findings from the code that shape the plan

- `compare._outer_sql` already returns per group and cut each side's row count
  (`__s_k<j>_c_rows`, `__s_k<j>_d_rows`); `cut_flags` always yields at least one
  cut for a comparison with `rows` (`_cuts` returns `[{}]`). So every group can
  carry exact per-cut counts. The value-column `n`/`sum` stats and the
  `count_students` branch exist only for sizing.
- `link_cells` reads `triage._entries(run)`, which lists only open groups. A
  group a `group:` decision closed sits in `run.applied.quiet`; a group a cause
  decision decides stays open with `decided` marked. Coverage must read both.
- `decisions.apply` closes a comparison's `CellDiff` with a `cells: true`
  decision; `CellDiff` is one per comparison. Splitting it by kind (`cells`,
  `formula`) keeps `open_cells` / `quiet_cells` and their JSON.
- `triage`'s explanation runner (`confirm.run_stored`) already dry-runs every
  explanation it will run before running any and records a dry-run failure as
  "not run". That covers what `confirm.check_proofs` did for `prove --check`, so
  `check_proofs` and `pipeline.current_row_sides` are deleted, not moved.
- `pipeline._compare_one` builds and runs each query in turn. Pricing every
  query first needs a plan/execute split; the metadata lookups that decide which
  queries exist (`fact_builds`, `network_schools`, `changed_between`) run before
  the price, as today.
- `bq.Warehouse.script` runs the save script as one job; a temp table's reads
  cannot be dry-run before it exists. `pipeline.inline_unmatched` (the same join
  as one SELECT) prices the scan that dominates it.
- `run.moment` is read by `confirm.require_saved`, `proof_sql`, `run_proof`,
  `trace` (`build=run.moment`), `triage.value_check`, `answers` (expiry,
  `moment`) and `report`. Per-comparison moments go through
  `RunResult.moment_of(comparison_id)`.
- `pipeline.run` and `compare.py` share a name space (`from . import compare`),
  so the Python function keeps the name `run`; renames are user-facing (CLI,
  YAML keys, folder, messages, JSON keys the skills read), not module or
  function names.
- `trace._Bucket.children` already skips a model it cannot read; what stops a
  whole bucket is a failed level query (`runner.level` → None) or a failed dry
  run (`Stopped`), both of which can come from one model among several frames.
- `#6181` items 7 and 8 (comments on the issue) are `run --comparison` and
  progress output; items 12 and 14 are the tableau fixes.

## File Structure

```text
P/checks.py        deleted (anchors, identities, strongest check)
P/coverage.py      new: place a group's rows in a cell; why a cell cannot be placed
P/latest.py        new: each comparison's latest result in <cache>/<view>/latest/
P/compare.py       Group.cut_rows, CellDiff.kind, rows-only stats; sizing SQL gone
P/config.py        refusals, RowSpec.reduce, Decision.formula, renamed keys
P/pipeline.py      plan/price/execute, workbook check, subset, stale, compose, reduce
P/confirm.py       link_cells by coverage; sizing and check_proofs gone
P/decisions.py     formula decisions
P/triage.py        formula item, #6346 labels, stale list, progress lines
P/trace.py         skip-and-continue, model chain, MAX_LEVELS 5
P/report.py        verdict, Ticker progress lines, moments, formula wording
P/answers.py       formula questions, per-comparison moments, explanations key
P/tableau.py       _nested_under, export_date
P/preflight.py     names comparisons whose cells cannot be covered
P/cli.py           commands renamed, flags added and removed
.claude/skills/cube-validation/SKILL.md, cube-builder/SKILL.md,
cube-validation-answers/SKILL.md, scripts/CLAUDE.md
```

---

### Task 1: Remove `check-api`

**Files:**

- Modify: `P/cli.py` (subparser `check-api`, its `_dispatch` branch, module
  docstring command list), `P/pipeline.py` (`check_api`, `_api_checks`, `_same`,
  `API_DECIMALS`, `CHECK_API_CUTS`)
- Test: `T/test_cli.py` (delete `test_check_api_accepts_a_dev_dataset`,
  `test_check_api_agrees_on_three_cuts`,
  `test_check_api_prices_the_api_side_before_it_loads`,
  `test_check_api_refuses_disagreement`,
  `test_check_api_refuses_when_a_table_rebuilt`)

**Interfaces:**

- Consumes: nothing.
- Produces: no `check-api` command. `pipeline._priced_load` and `_load_value`
  stay until Task 2 (anchors use them).

- [ ] **Step 1: Write the failing test** in `T/test_cli.py`:

```python
def test_check_api_is_not_a_command(fakes, tmp_path, capsys):
    assert cli.main(["check-api", str(_file(tmp_path))]) == 2
    assert "invalid choice: 'check-api'" in capsys.readouterr().err
```

- [ ] **Step 2: Run to fail.** Expected: FAIL (exit 0).
- [ ] **Step 3: Delete** the subparser, dispatch branch and the 5 pipeline names
      above, and the 5 tests. Keep `changed_between` imports other code uses.
- [ ] **Step 4: Run**
      `uv run --with duckdb pytest tests/scripts/cube_validation/ -q`. Expected:
      all pass.
- [ ] **Step 5: Commit** `P/cli.py P/pipeline.py T/test_cli.py`:
      `refactor(cube): drop the check-api command`.

---

### Task 2: Remove anchors and identities

**Files:**

- Delete: `P/checks.py`, `T/test_checks.py`
- Modify: `P/config.py` (`Anchor`, `Identity`, `_anchor`, `_identity`,
  `ViewConfig.anchors`, `ViewConfig.identities`, `load_view_config`, module
  docstring), `P/pipeline.py` (`_anchors_and_identities`, `_identity_cuts`,
  `_priced_load`, `_load_value`, `_measures`, `_extra_sections`, `run`,
  `missing_members`, `prove_check`'s anchor filter, `reapply`,
  `_run_from_json`), `P/report.py` (`MeasureResult.strongest`,
  `RunResult.findings`, `_verdict_text`, `render_local`, `render_review_issue`,
  `_review_body`), `P/cli.py` (parser description)
- Test: `T/test_config.py`, `T/test_report.py`, `T/test_cli.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `MeasureResult(measure, verdict, cells, open_groups, open_gaps, open_cells)`
    (no `strongest`); `RunResult` has no `findings`.
  - `pipeline.verdict(cells: dict[str, int], open_groups: int, open_gaps: int, open_cells: int) -> str`:
    `"validated"` when every cell verdict is `pass` or `dashboard_filtered` and
    all 3 counts are 0, else `"differs"`. `run` and `reapply` both call it, so a
    decision that closes the last item flips a measure to validated offline.
  - `config.load_view_config` raises `ConfigError` on a root `anchors` or
    `identities` key:
    `"{path}: anchors: delete this block; the validator checks Cube against dashboards only"`
    (same for `identities`).
  - `time_dimension` is required only when a comparison has `rows`: message
    `"is required when comparison rows are set"`.

- [ ] **Step 1: Write the failing tests.**

`T/test_config.py` (replace `test_anchors_need_a_time_dimension` and
`test_time_dimension_is_optional_without_anchors_or_rows`):

```python
@pytest.mark.parametrize("key", ["anchors", "identities"])
def test_an_anchor_or_identity_block_is_refused(tmp_path, key):
    path = _write(tmp_path, BASE + f"{key}: []\n")
    with pytest.raises(ConfigError, match=f"{key}: delete this block"):
        load_view_config(path)


def test_time_dimension_is_optional_without_rows(tmp_path): ...
```

`T/test_report.py` (replace `test_consistent_only_measure_reads_not_validated`,
`test_passing_anchor_not_listed_and_count_masking` (keep its masking half),
`test_local_result_says_anchors_read_current_data`):

```python
def test_a_measure_with_an_open_item_reads_differs():
    assert pipeline.verdict({"pass": 3}, 1, 0, 0) == "differs"
    assert pipeline.verdict({"pass": 3}, 0, 0, 0) == "validated"
    assert pipeline.verdict({"pass": 2, "dashboard_filtered": 1}, 0, 0, 0) == "validated"
    assert pipeline.verdict({"pass": 2, "differs": 1}, 0, 0, 0) == "differs"
```

`T/test_cli.py`: rename `test_run_reports_cells_proofs_and_identity` to
`test_run_reports_cells_and_proofs` and drop its identity assertions; delete
`test_run_reads_each_identity_cut_in_one_load`; add

```python
def test_reapply_marks_a_measure_validated_once_its_last_group_is_decided(fakes, tmp_path):
    # run with one open group, write a group decision covering it, reapply:
    # the measure line in result.md reads "validated".
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** Delete `checks.py`; `report.py` imports nothing
      from it. `render_local` prints ``- `<measure>`: <verdict> (<cells>)`` plus
      the open-item suffixes it prints today; drop the "Anchors and identities
      read Cube's data…" lines, the `judge the anchor` handling in
      `render_review_issue`, and "Anchor findings" in `_review_body`.
      `_extra_sections(cells)` keeps `## Cells` only. `_run_from_json` builds
      `MeasureResult` from `measure`, `verdict`, `cells`, `open_*`; an old
      run.json with `strongest` or `findings` raises `TypeError`/`KeyError` and
      is refused by the existing `_older` path.
- [ ] **Step 4: Run** the whole suite. Expected: all pass.
- [ ] **Step 5: Commit** the files above (and `git rm` of the 2 deleted):
      `refactor(cube): drop anchors and identities; a measure is validated or differs`.

---

### Task 3: Remove cell sizing; groups carry per-cut row counts

**Files:**

- Modify: `P/compare.py` (`Group`, `_outer_sql`, `_stat_names`,
  `reconcile_script`, `_with_students`, `cell_students_sql`,
  `_student_branches`, `_cell_labels`, `_saved_joined`, `groups_from`,
  `cell_rows_from`, `_side_stats`), `P/config.py` (`RowSpec.cell`, `ROW_CELLS`,
  `_comparison`, `_decision`), `P/pipeline.py` (`_Sides`, `save_script`,
  `_compare_one`, `run`, `_group`, `_run_from_json`), `P/report.py`
  (`RunResult.cell_rows`, `RunResult.cell_students`), `P/confirm.py`
  (`_counts_rows`, `_SIGN`, `_per_cut`, `_sizable`, `_rebuilt`,
  `_students_rebuilt`, `_reproduces`, `link_cells`), `P/answers.py`
  (`cell_causes`, `_ROWS_SIDE`)
- Test: `T/test_compare.py`, `T/test_config.py`, `T/test_confirm.py`,
  `T/test_cli.py`, `T/test_pipeline_slices.py`, `T/test_answers.py`

**Interfaces:**

- Consumes: nothing new.
- Produces:
  - `compare.Group.cut_rows: tuple[tuple[str, int, int], ...] = ()`: per cut
    label (`pipeline.cut_label`), the group's rows on the Cube side and on the
    dashboard side (the dashboard counts only rows its filters keep, as the
    stats do now). Not part of `triage._open_key`.
  - `compare.groups_from(comparison_id: str, result_rows: list[dict], cut_labels: Sequence[str] = ()) -> list[Group]`
    fills `cut_rows` from `__s_k<j>_{c,d}_rows`.
  - `compare._outer_sql` returns only `__s_[k<j>_]{c,d}_rows` stats; no `_n<i>`
    or `_sum<i>`. `reconcile_script` loses `students`.
  - `RunResult` has no `cell_rows` or `cell_students`; `_run_from_json` ignores
    those keys in an old run.json.
  - `config.load_view_config` refuses `rows.cell`:
    `"rows.cell: delete it; cells close by coverage"`; and a decision with
    `cells`:
    `"cells: delete this decision; triage closes covered cells itself"`.
    `Decision.cells` is gone.
  - `confirm.link_cells(run, items, comparison=None, cfg=None, open_cells=None) -> dict[str, tuple[int, int]]`:
    per cell-set item, (cells not linked, all cells). Linking keeps today's
    `_in_cut`/`_in_cells` match with no size check; Task 5 replaces the match
    with exact placement.
  - `answers.cell_causes` decides "every row of `g` lies in `cell`" from
    `g.cut_rows`: the group's rows on its side under the cell's cut equal its
    rows on that side under every cut, and are more than 0.

- [ ] **Step 1: Write the failing tests.**

`T/test_compare.py` (on `duck`; replaces
`test_cell_students_count_each_student_once_per_side_and_cell` and
`test_cell_students_count_the_dashboard_s_cell_and_its_kept_rows_per_cut`):

```python
def test_each_group_carries_its_rows_per_cut_on_each_side(duck):
    # 2 cuts (Region=Newark, Region=Miami); a cube_only row in Newark, a
    # dashboard_only row in Miami, a dashboard_filtered row in Newark.
    groups = compare.groups_from("c1", duck.rows(compare.reconcile_sql(...)),
                                 ['{"Region": "Newark"}', '{"Region": "Miami"}'])
    by_bucket = {g.bucket: g for g in groups}
    assert by_bucket["cube_only"].cut_rows == (('{"Region": "Newark"}', 1, 0), ('{"Region": "Miami"}', 0, 0))
    assert by_bucket["dashboard_only"].cut_rows == (('{"Region": "Newark"}', 0, 0), ('{"Region": "Miami"}', 0, 1))
    assert by_bucket["dashboard_filtered"].cut_rows[0] == ('{"Region": "Newark"}', 1, 0)


def test_the_reconcile_returns_no_value_sums(duck):
    row = duck.rows(compare.reconcile_sql(...))[0]
    assert not any(k.endswith(("_n0", "_sum0")) for k in row)
```

`T/test_config.py`:

```python
def test_rows_cell_is_refused(tmp_path):  # replaces test_rows_cell_defaults_to_the_mean_and_takes_count_students
    with pytest.raises(ConfigError, match="rows.cell: delete it"): ...

def test_a_cells_decision_is_refused(tmp_path):  # replaces test_cells_decision_loads / _takes_no_group
    with pytest.raises(ConfigError, match="cells: delete this decision"): ...
```

`T/test_pipeline_slices.py`: a `_Sides` slice with a group carrying `cut_rows`
round-trips through `to_json`/`from_json` with tuples restored.

`T/test_cli.py`: `test_run_saves_differing_cells_and_their_pinned_sql` asserts
run.json has no `cell_rows`/`cell_students` key and its open groups carry
`cut_rows`; delete
`test_run_counts_a_cells_students_under_its_dashboard_filters`.

`T/test_confirm.py`: delete
`test_cells_refuse_when_the_difference_is_not_the_proven_rows`,
`test_a_student_count_cell_links_when_its_students_rebuild_both_sides`,
`test_a_rate_cell_links_when_its_rows_rebuild_both_sides`,
`test_a_run_saved_before_cell_sums_links_and_says_sizes_went_unchecked`,
`test_two_cell_sets_link_on_a_run_saved_before_cell_sums`; keep the others
(`test_cells_confirm_when_every_differing_cell_lies_in_proven_groups`,
`test_cells_refuse_with_the_count_left_outside_proven_groups`,
`test_cells_link_only_to_groups_under_their_cut`,
`test_a_cells_refusal_names_each_open_cell_and_why`) passing.

`T/test_answers.py`: the floor in `cell_causes` reads `cut_rows` (adjust the
fixture run to carry them).

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** In `_compare_one`, call
      `compare.groups_from(comparison.id, result, [label for label, _, _ in flags])`
      and drop the `students`/`counted` split. Delete `cell_students_sql`,
      `_with_students`, `_student_branches`, and `_cell_labels` (its only other
      use is `_saved_joined`'s `extra`, which the saved select never reads).
      `pipeline._group` and `_Sides.from_json` restore `cut_rows` as a tuple of
      tuples. `link_cells` drops the `counts` / `students_kind` / `sums`
      branches, the `gap`, `unsized`, `unbuilt` counters and their evidence
      text; its docstring describes the match only.
- [ ] **Step 4: Run** the whole suite. Expected: all pass.
- [ ] **Step 5: Commit** the files above:
      `refactor(cube): drop cell sizing; keep each group's rows per cut`.

---

### Task 4: Remove `prove --check` and `check_proofs`

**Files:**

- Modify: `P/cli.py` (`--check` on `prove`, its dispatch branch; `--comparison`
  becomes required), `P/confirm.py` (`check_proofs`), `P/pipeline.py`
  (`current_row_sides`; `prove_check` renamed `workbook_check`, prints nothing),
  `P/compare.py` (`unmatched_rows_sql` docstring no longer names
  `prove --check`)
- Test: `T/test_cli.py`, `T/test_confirm.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  `pipeline.workbook_check(cfg: ViewConfig, comparisons: list[Comparison], *, tbl: tableau.Tableau, cube: Cube) -> list[str]`:
  the same stale lines `prove_check` built (members Cube's `/meta` lacks;
  formulas, datasource or a missing `workbook_updated_at`), for `comparisons`
  only, printing only "republished …, sheet unchanged" lines. Task 7 calls it.
  `pipeline.inline_unmatched` stays (Task 7 prices with it).

Decision: `triage`'s explanation runner already dry-runs every explanation it
will run before spending and records a rejected one as "not run (…)", so
`check_proofs`' dry runs are covered there and are deleted, not moved.

- [ ] **Step 1: Write the failing tests.** In `T/test_cli.py`:

```python
def test_prove_takes_no_check_flag(fakes, tmp_path, capsys):
    assert cli.main(["prove", str(_file(tmp_path)), "--check"]) == 2

def test_workbook_check_lists_only_the_comparisons_asked(fakes, tmp_path):
    # 2 comparisons on a republished workbook whose formulas changed;
    # workbook_check(cfg, [first]) names the first only.
```

Rewrite the `test_prove_check_*` tests (lines ~1964-2048) to call
`pipeline.workbook_check` directly and assert on the returned lines; delete
`test_prove_check_lists_stored_proofs_bigquery_rejects` and the 3
`test_check_proofs_*` tests in `T/test_confirm.py`.

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** Between this task and Task 7 nothing calls
      `workbook_check`; that gap lives only inside this PR.
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** the files above:
      `refactor(cube): drop prove --check; keep its workbook check for run`.

---

### Task 5: Cells close by coverage

**Files:**

- Create: `P/coverage.py`, `T/test_coverage.py`
- Modify: `P/confirm.py` (`link_cells`, `_in_cut`, `_in_cells`, `_agrees`,
  `_dash_value`, `open_cell_lines`, `_unlinked`, `run_confirm`), `P/triage.py`
  (`mark_decided`), `P/answers.py` (`cell_causes`), `P/cli.py`
  (`triage confirm --cells` removed), `P/preflight.py` (`report`),
  `P/pipeline.py` (`run` prints unplaceable comparisons)
- Test: `T/test_confirm.py`, `T/test_triage.py`, `T/test_preflight.py`,
  `T/test_cli.py`

**Interfaces:**

- Consumes: `Group.cut_rows` (Task 3).
- Produces (`P/coverage.py`):
  - `unplaceable(comparison: Comparison) -> str | None`: why no cell of the
    comparison can be placed: `"the comparison has no rows"`, or
    `"its dims <names> are part of the row grain"` when a dim is not among
    `pipeline.group_dims`. None otherwise.
  - `has_rows_in(g: Group, cell: dict) -> bool`: the group has at least 1 row in
    the cell: under the cell's cut, its Cube-side rows are > 0 and its own
    columns agree with every cell dim, or its dashboard-side rows are > 0 and
    the dashboard's columns (its `d:` columns for `dims_differ`, else its own)
    agree. Values compare by `pipeline._key`; a group with no `cut_rows` for the
    cell's cut has no row there.
  - `placed(cell: dict, groups: list[Group], comparison: Comparison) -> list[Group] | None`:
    the groups with a row in the cell, or None when the cell cannot be placed
    (`unplaceable`, or a cell dim missing from the groups' columns).
  - `confirm.link_cells(run, items, comparison=None, cfg=None, open_cells=None) -> dict[str, tuple[int, int]]`:
    groups are the open items' groups and the run's quiet groups
    (`run.applied.quiet`). A cell is covered when `placed` returns groups and
    each is either quiet or an open item in `cause`. A cell with no group in it
    (`placed` returns `[]`) stays open here with why
    `"no unmatched row lies in it"`; Task 6 moves such cells to the formula
    item. A cell set with every cell covered moves to `cause` with
    `proof={"kind": "cells", "groups": [open item ids], "closed": [quiet _open_keys]}`;
    otherwise it stays in `investigate` with each open cell's why:
    `"<n> of its <m> groups are not in cause"`,
    `"cannot be placed: <unplaceable reason>"`, or
    `"no unmatched row lies in it"`.
  - `triage.mark_decided` also marks a `cells` item: `decided` is true when
    every id in `proof.groups` is an item with `decided` true (`closed` groups
    are decided by their `group:` decision).
  - CLI: `triage confirm` loses `--cells`; `--bucket` is required. Every
    `triage confirm` and every `triage` re-links cells, as now.
  - `preflight.report` prints, per comparison `unplaceable` names, one line
    `"    Cells cannot be covered: <why>"` beside "Before prove"; `run` prints
    `"Comparison <id>: its cells cannot be covered (<why>); its differing cells stay open."`
    before `_run_folder`. Neither refuses.

- [ ] **Step 1: Write the failing tests** in `T/test_coverage.py` (pure, no
      warehouse) and the callers' files:

```python
def test_a_group_with_no_rows_under_the_cell_cut_does_not_cover_it():
    g = Group("c1", (("region", "Miami"),), "cube_only", 4, 4,
              cut_rows=(('{"Grade": "5"}', 4, 0), ('{"Grade": "6"}', 0, 0)))
    cell = {"cut": '{"Grade": "6"}', "dims": [["region", "Miami"]]}
    assert coverage.placed(cell, [g], SPEC) == []

def test_a_dims_differ_group_sits_in_both_its_cells(): ...
    # Cube side in region=Miami, dashboard side in d:region=Newark: in both cells

def test_a_dashboard_filtered_group_sits_in_cube_s_cell_only(): ...

def test_a_cell_on_a_grain_dim_stays_open_and_says_why():
    # SPEC with dims [student_number] in the grain
    assert coverage.unplaceable(spec) == "its dims student_number are part of the row grain"
    assert coverage.placed(cell, groups, spec) is None
```

`T/test_confirm.py`:

```python
def test_a_cell_covered_by_a_decided_group_and_a_proven_one_closes(tmp_path, monkeypatch):
    # one group quiet by a group: decision, one open group in cause: the cell set
    # moves to cause, proof.closed holds the quiet group's key.

def test_a_cell_with_one_unproven_group_stays_in_investigate(tmp_path, monkeypatch):
    # evidence: "1 of 2 differing cells ..." and the open cell's why "1 of its 2 groups are not in cause"
```

Replace `test_cells_link_only_to_groups_under_their_cut` with a version whose
groups carry `cut_rows`. `T/test_triage.py`:
`test_a_cells_item_is_decided_once_every_covering_group_is`. `T/test_cli.py`:
`test_triage_confirm_takes_no_cells_flag` (exit 2). `T/test_preflight.py`:
`test_preflight_names_a_comparison_whose_cells_cannot_be_covered`.

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement** `P/coverage.py` and rewire `link_cells`;
      `answers.cell_causes` takes its groups from `coverage.placed` instead of
      `confirm._in_cut`/`_in_cells`, which are deleted with `_agrees` and
      `_dash_value`. `link_cells` posted evidence counts cells with
      `report.mask`.
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** `P/coverage.py T/test_coverage.py` and the modified
      files:
      `feat(cube): close a differing cell when every group with a row in it is proven or decided`.

---

### Task 6: The formula difference

**Files:**

- Modify: `P/compare.py` (`CellDiff.kind`), `P/pipeline.py` (`_cell_diffs`,
  `_cell_diff`), `P/config.py` (`Decision.formula`, `_decision`; the `cells:`
  refusal now says
  `"cells: delete this decision; covered cells need none, and a formula difference takes formula: true"`),
  `P/decisions.py` (`apply`), `P/triage.py` (`_entries`, `_open_key`, `suggest`,
  `PROOF_KINDS`), `P/confirm.py` (`link_cells` skips `formula` items),
  `P/report.py` (`_decision_line`, `render_local`, `_questions`,
  `defined_comparisons`), `P/answers.py` (`_covers`, `_STUB_KEYS`,
  `questions_json` definitions for `formula`)
- Test: `T/test_decisions.py`, `T/test_config.py`, `T/test_triage.py`,
  `T/test_cli.py`, `T/test_report.py`, `T/test_answers.py`

**Interfaces:**

- Consumes: `coverage.placed` (Task 5).
- Produces:
  - `compare.CellDiff.kind: str = "cells"` (`"cells"` or `"formula"`).
  - `pipeline._cell_diffs` splits each comparison's differing cells: a cell
    `coverage.placed` returns `[]` for is a formula cell; every other cell
    (groups in it, or unplaceable) is a `cells` cell. It returns up to 2
    `CellDiff`s per comparison. The formula one's `causes` start with
    `"<n> differing cells hold no unmatched row"` and end with the recorded
    `definitions`, as `candidate_causes` builds them.
  - `config.Decision.formula: bool = False`; `formula` joins the exclusive keys
    (`group`, `missing_cut`, `missing_filter`, `formula`, `cause`); it needs
    `comparison` and `fingerprints` like a group decision.
  - `decisions.apply`: a `formula` decision quiets its comparison's `formula`
    `CellDiff` while both fingerprints hold (else `reconfirm`; none →
    `no_longer_needed`; 2 on one comparison → `ValueError`). A `cells`
    `CellDiff` is never quieted by a decision.
  - `triage._entries`: item id `<id>:formula`, kind `formula`, stub
    `{"comparison": id, "formula": True}`; `_open_key` includes the kind.
    `suggest` puts it in `cause` with
    `cause=[{"side": "both", "step": "formula", "label": "differing cells hold no unmatched row", "n_rows": None}]`,
    `proof={"kind": "formula", "fingerprint": sha256 of the comparison's run fingerprints}`,
    evidence
    `"<n> differing cells hold no unmatched row: every row in them matched on both sides"`,
    posted with `<n>` as `report.mask(n)`. `PROOF_KINDS` adds `"formula"`.
  - `report`: decision line `` `<id>` (<comparison> formula, <call>) ``; the
    review question part reads
    `` `<comparison>` in `<view>`: <mask(n)> cells differ while every row in them matches; which definition is right? ``,
    kind `"formula"`, and its comparison's `definitions` show (kinds `group`,
    `cause`, `formula` in `defined_comparisons`).
  - `answers._covers`: `d.formula` matches `stub.get("formula") is True`;
    `_STUB_KEYS` swaps `"cells"` for `"formula"`.

- [ ] **Step 1: Write the failing tests.**

```python
# T/test_decisions.py (replace the 3 test_cells_decision_* tests)
def test_a_formula_decision_quiets_its_comparison_s_formula_cells(): ...
def test_a_formula_decision_reconfirms_when_sql_changed(): ...
def test_a_formula_decision_never_quiets_a_cells_diff(): ...

# T/test_cli.py
def test_a_cell_whose_rows_all_match_is_a_formula_difference(fakes, tmp_path):
    # cells differ, the reconcile returns only `match` rows for that cell:
    # run.json applied.open_cells holds a CellDiff kind "formula"; triage puts
    # "<id>:formula" in cause with proof kind "formula".

def test_a_cell_that_gains_a_row_leaves_the_formula_claim(fakes, tmp_path):
    # run 1: formula cells A and B, decision formula: true written via add-decisions.
    # run 2: an unproven cube_only group lands in A: A is in "<id>:cells"
    # (investigate), B stays quiet under the decision.

def test_an_unplaceable_cell_is_never_a_formula_difference(fakes, tmp_path): ...

# T/test_report.py
def test_a_formula_question_shows_both_definitions_and_masks_its_count(): ...
```

`T/test_config.py`: `test_a_formula_decision_loads` and
`test_formula_and_group_are_exclusive`.

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** `link_cells` skips items of kind `formula`.
      `_cell_diff` (JSON) reads `kind` with default `"cells"`.
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** the files above:
      `feat(cube): a differing cell whose rows all match is a formula difference for the owner`.

---

### Task 7: `run` checks the workbook and prices every query before it spends; progress lines

**Files:**

- Modify: `P/pipeline.py` (`_compare_one` split, `_compare_all`, `run`,
  `_Sides`), `P/report.py` (`Ticker`), `P/cli.py` (`run` signs in to Tableau)
- Test: `T/test_cli.py`, `T/test_report.py`

**Interfaces:**

- Consumes: `pipeline.workbook_check` (Task 4), `pipeline.inline_unmatched`.
- Produces:
  - `report.Ticker(clock: Callable[[], datetime], started: datetime)` with
    `say(step: str, comparison: str, spent: float) -> str`: prints and returns
    `"[{now:%H:%M:%S} UTC +{elapsed}] {step} {comparison}: ${spent:.2f} spent"`
    with `flush=True`; elapsed is `{m}m{ss}s`, or `{h}h{mm}m{ss}s` from 1 hour.
    No row value ever goes in it.
  - `pipeline._Plan` (dataclass): `comparison`, `fingerprints`,
    `cuts: list[_CutPlan]` (`label`, `dash_sql`, `cube_sql` wrapped,
    `unfiltered_sql | None`), `rows: RowSides | None`, `moved`, `shared`,
    `students_sql | None`, `cube_tables`, `live`; and `queries() -> list[str]`:
    every query that bills, the save script stood in for by
    `inline_unmatched(cfg, comparison, rows)`.
  - `pipeline._plan_one(cfg, comparison, *, wh, cube, build, schools, moved) -> _Plan`:
    compile, expand and check `changed_between` (the both-sides-moved refusal
    moves here, before any spend). No billed query.
  - `pipeline._execute(cfg, plan, *, wh, build, prices: list[float]) -> _Sides`:
    runs the plan's queries as `_compare_one` does today; `cell_sql_usd` comes
    from `prices`.
  - `pipeline.run(..., tbl: tableau.Tableau, ticker: report.Ticker | None = None)`:
    after `missing_members`, calls
    `workbook_check(cfg, comparisons, tbl=tbl, cube=cube)` and refuses with
    `"workbook changed since its rebuild check: <lines>; rebuild the sheet for <ids>"`
    (worded with old names until Task 12) before `_run_folder`. Inside the
    budget, plans every comparison not taken from a checkpoint, dry-runs each
    plan query one at a time (`wh.estimate`), prints
    `"Compare: <n> queries, $<total> (dry run)"`, and calls
    `wh.refuse_past_caps(total)` before the first billed query. After each
    comparison, `ticker.say("compare", comparison.id, wh.spent)`.
  - The "proof is more than 7 days old … `prove --check`" warning is removed:
    `run` now checks the workbook itself.

Decisions: the save script is priced by a dry run of its join
(`inline_unmatched`), since its temp table cannot be dry-run before it exists;
its 2 reads of that table stay under `wh.rows`' `maximum_bytes_billed`. The
metadata lookups (`fact_builds`, `network_schools`, `changed_between`) run
before the price because they decide which queries exist. The workbook check
covers every confirmed comparison (spec: "for each confirmed comparison").

- [ ] **Step 1: Write the failing tests** in `T/test_cli.py`:

```python
def test_run_refuses_a_changed_workbook_before_any_query(fakes, tmp_path, capsys):
    fakes.tbl.updated = datetime(2026, 10, 30, tzinfo=timezone.utc)  # after the proof
    fakes.tbl.twb = <sheet_formats.twb with a changed formula>
    assert cli.main(["run", str(_file(tmp_path))]) == 1
    assert "rebuild" in capsys.readouterr().err
    assert not [q for q in fakes.bq.ran if "fct_f" in q or "rpt_d" in q]

def test_run_prices_every_query_first_and_refuses_over_the_cap(fakes, tmp_path, capsys):
    fakes.bq.cost = lambda sql: 2.0 if "rpt_d" in sql else 0.0
    assert cli.main(["run", str(_file(tmp_path)), "--max-usd", "1"]) == 1
    assert not [q for q in fakes.bq.ran if "rpt_d" in q or "fct_f" in q]

def test_run_prints_the_priced_total_then_a_progress_line_per_comparison(fakes, tmp_path, capsys):
    cli.main(["run", str(_file(tmp_path))])
    out = capsys.readouterr().out
    assert "Compare: " in out and "(dry run)" in out
    assert re.search(r"\[\d\d:\d\d:\d\d UTC \+\d+m\d\ds\] compare c1: \$\d+\.\d\d spent", out)
```

`T/test_report.py`:

```python
def test_a_ticker_line_shows_clock_elapsed_step_and_spend():
    t = report.Ticker(lambda: datetime(2026, 11, 14, 15, 4, 5, tzinfo=timezone.utc),
                      datetime(2026, 11, 14, 13, 2, 0, tzinfo=timezone.utc))
    assert t.say("sort", "c1", 0.5) == "[15:04:05 UTC +2h02m05s] sort c1: $0.50 spent"
```

Existing resume tests (`test_a_stopped_run_resumes_to_the_same_result` and
neighbours) must still pass: a resumed run plans and prices only the comparisons
without a holding checkpoint.

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** `cli` wraps `pipeline.run` in
      `with tableau_session() as tbl:` and passes
      `ticker=report.Ticker(utcnow, utcnow())`.
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit**
      `P/pipeline.py P/report.py P/cli.py T/test_cli.py T/test_report.py`:
      `feat(cube): run checks the workbook and prices every query before it spends`.

---

### Task 8: `run --comparison`, each comparison's latest result, and the stale list

**Files:**

- Create: `P/latest.py`, `T/test_latest.py`
- Modify: `P/pipeline.py` (`run`, `_run_folder`'s resume message,
  `_compare_all`, `_run_from_json`, `latest_run`, `review`; new
  `stale_comparisons`), `P/report.py` (`RunResult.moments`, `entries`,
  `missing`, `moment_of`; `render_local`; `render_review_issue`), `P/confirm.py`
  (`require_saved`, `run_stored`, `_run_one`, `run_confirm`: per-comparison
  moment), `P/trace.py` (`_plan`, `Prepared.row_sides`: per-comparison moment),
  `P/triage.py` (`_moment`, `proven_triage`, `run_triage`), `P/answers.py`
  (expiry and `moment` per question from its comparisons), `P/cli.py`
  (`run --comparison`, `--all`)
- Test: `T/test_latest.py`, `T/test_cli.py`, `T/test_confirm.py`,
  `T/test_triage.py`, `T/test_answers.py`, `T/test_report.py`

**Interfaces:**

- Consumes: `_Plan` / `_execute` (Task 7), `checkpoint_fingerprint`,
  `side_fingerprints`.
- Produces:
  - `P/latest.py`:
    - `DIR = "latest"`; a result lives at `<cache>/<view>/latest/<id>.json`.
    - `@dataclass(frozen=True) class Latest: moment: Build; fingerprint: str; entry: str; ran_at: str; data: dict`
      (`data` is the comparison's `_Sides.to_json()` slice: counts, SQL and
      fingerprints, no student row).
    - `entry_fingerprint(comparison: Comparison) -> str`: sha256 of
      `json.dumps(dataclasses.asdict(comparison), sort_keys=True, default=str)`;
      covers the entry and its rebuild check.
    - `write(view_dir: Path, comparison_id: str, result: Latest) -> None`
      (atomic, as `checkpoints._write_json`),
      `read_all(view_dir: Path) -> dict[str, Latest]`.
  - `pipeline.stale_comparisons(cfg, comparisons, results: dict[str, Latest], *, wh, cube, schools, now: datetime) -> dict[str, str]`:
    per confirmed comparison whose result is missing or stale, why:
    `"never compared"`, `"its entry or rebuild check changed"`,
    `"Cube's SQL changed"`, `"the dashboard SQL changed"`. Stale means
    `checkpoint_fingerprint(c, side_fingerprints(..., build=Build(now, now, "now")))`
    differs from the stored `fingerprint`; the side named comes from comparing
    the stored slice's `fingerprints[c.id]` with today's. Masked moments make a
    new build alone not stale. Compile and expand only; its one query is
    `network_schools`.
  - `pipeline.run(..., only: list[str] | None = None, every: bool = False)`:
    `only` (`--comparison`, repeatable, unknown id refused) runs those; `every`
    (`--all`) runs every confirmed one; neither runs `stale_comparisons`' keys,
    printing each with its why first, and with none prints
    `"Every comparison's latest result is current; pass --all to compare every one again."`
    and returns without writing. After each comparison it writes its `Latest`;
    then composes `run.json` in this run's folder from every confirmed
    comparison's latest result, merged in config order.
  - `RunResult.moments: dict[str, Build]` (every composed comparison's moment),
    `entries: dict[str, str]` (`entry_fingerprint` at compare time),
    `missing: list[str]` (confirmed comparisons with no result), and
    `moment_of(comparison_id: str) -> Build` (`moments.get(id, moment)`).
    `moment` stays this compare process's build (its folder, its cost).
  - Every reader of `run.moment` for one comparison's rows uses
    `run.moment_of(comparison.id)`: `confirm.require_saved` (and its message,
    which names `run --comparison <id>`), `proof_sql`, `run_proof`, the trace's
    `_Side`/`row_sides`. `triage.value_check` keeps `run.moment`.
  - `triage._moment(run)` adds `"moments": {id: run_stamp}`, so a recomposed run
    needs a new triage. `run_triage` writes `"stale": stale_comparisons(...)` to
    `triage.json` and prints each. `proven_triage` refuses when `run.missing`,
    `loaded["stale"]`, or an `entry_fingerprint` differing from `run.entries`
    (offline) is non-empty:
    `"<view>: comparison <id> <why>; compare it, then sort"` (old command words
    until Task 12).
  - `render_local` prints `Moment:` once when every comparison shares it, else
    one `- <id>: <start> to <end> UTC` line per comparison; the review issue
    lists each comparison's moment the same way. `answers.questions_json`'s
    `moment` and `expires` read the earliest moment among each question's
    comparisons.

Decisions: results are copied into `latest/`, not pointed at run folders, since
`checkpoints.clear` on a restart of the same moment would delete a slice a
pointer still names. The spec's "`run --comparison` replaces entries in a run at
the same moment" (_Calls made_) is superseded by its section 3a: each comparison
keeps its own moment.

- [ ] **Step 1: Write the failing tests.**

```python
# T/test_latest.py
def test_a_result_round_trips_with_its_moment(tmp_path): ...
def test_the_entry_fingerprint_changes_with_the_rebuild_check(): ...

# T/test_cli.py
def test_run_comparison_runs_only_that_one_and_keeps_the_others(fakes, tmp_path):
    # 2 comparisons run at build 1; `run --comparison c2` at build 2:
    # run.json moments: c1 -> build 1, c2 -> build 2; only c2's queries ran.

def test_a_plain_run_runs_only_stale_and_never_run_comparisons(fakes, tmp_path, capsys): ...
def test_run_all_runs_every_comparison(fakes, tmp_path): ...
def test_a_new_build_alone_is_not_stale(fakes, tmp_path, capsys):
    # second plain run at a newer build: "Every comparison's latest result is current"
def test_a_changed_view_definition_is_stale(fakes, tmp_path, capsys):
    # fakes.bq.views["rpt_d"] changes between runs: c1 listed "the dashboard SQL changed"

# T/test_confirm.py
def test_an_explanation_reads_its_own_comparison_s_moment(tmp_path, monkeypatch):
    # run.moments {c1: b1, c2: b2}; the saved table id and as-of literal for c1 use b1

# T/test_triage.py
def test_ask_owner_refuses_a_missing_or_stale_comparison(tmp_path): ...
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.** `cli` adds `--comparison` (append) and `--all`
      (mutually exclusive with `--comparison`) to `run`. The resume message
      counts the selected comparisons, not every confirmed one.
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** `P/latest.py T/test_latest.py` and the modified files:
      `feat(cube): each comparison keeps its own latest result; run takes --comparison and --all`.

---

### Task 9: Sheet filters Cube might not offer (#6346)

**Files:**

- Modify: `P/triage.py` (`Suggestion`, `suggest`, `_as_json`, `_from_json`,
  `batch_lines`)
- Test: `T/test_triage.py`

**Interfaces:**

- Consumes: `triage._candidates`, `triage._missing_column`.
- Produces:
  - `Suggestion.default_call: str = ""`, written to `triage.json` as
    `default_call` and printed in the batch as `    default call: <call>`.
  - For every gap of kind `filter`, whatever pile it lands in, `candidates` are
    looked up and the first evidence line is one of:
    - candidates:
      ``"Cube offers it as `<m1>`, `<m2>`, unmapped: check before mapping it under `filters:`"``;
      `default_call` stays empty (the action is a mapping).
    - no candidate and `_missing_column(cfg, caption)` empty:
      `"Workbook-only field: no datasource column behind it"`, `default_call`
      `"deliberate"`.
    - no candidate and a datasource column: `"Cube has no member: a gap"`,
      `default_call` `"fix_cube"`.
  - The pile rules do not change; a candidate label wins over workbook-only.
  - Captions and member names only; no value is read.

- [ ] **Step 1: Write the failing tests.**

```python
def test_a_filter_that_filters_nothing_still_names_its_candidate_member(): ...
    # filter_notes says it filters nothing; docs hold a matching member:
    # pile filters_nothing, evidence[0] starts "Cube offers it as `v_region`"
def test_a_filter_with_no_member_and_no_column_is_workbook_only(): ...
    # default_call == "deliberate"
def test_a_filter_with_a_column_and_no_member_is_a_gap_for_cube(): ...
    # default_call == "fix_cube"
def test_a_candidate_beats_workbook_only(): ...
def test_the_default_call_round_trips_through_triage_json(): ...
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** `P/triage.py T/test_triage.py`:
      `feat(cube): label each unmapped sheet filter by whether Cube offers it`
      with body `Refs #6346`.

---

### Task 10: The trace gets past a model it cannot read; triage progress lines

**Files:**

- Modify: `P/trace.py` (`MAX_LEVELS`, `_Runner._run`, `_Runner.plan`,
  `_Bucket.blocked`, `_Bucket.children`, `_Bucket._run`, `_Bucket._descend`,
  `_Bucket.chain`, `_Bucket.run`/`stop`, `trace_run`), `P/confirm.py`
  (`run_stored` progress line), `P/triage.py` (`run_triage` passes a ticker)
- Test: `T/test_trace.py`, `T/test_confirm.py`

**Interfaces:**

- Consumes: `report.Ticker` (Task 7).
- Produces:
  - `MAX_LEVELS = 5`, still under the spend caps and `--trace-max-minutes`.
  - `class ModelFailed(Stopped)` raised by `_Runner._run` when a dry run fails
    and by `_Runner.plan` when one frame's SQL alone is too long; `Stopped` from
    the meter and `CostCapError` keep stopping the whole bucket.
  - `_Bucket.blocked: dict[str, str]`: model name → why (`"parse error"`,
    `"SQL too long"`, BigQuery's reason such as `"resourcesExceeded"` or
    `"invalidQuery"`, `"WITH RECURSIVE"`, `"past MAX_LEVELS"`). Only reason
    codes, never BigQuery's message (it can quote values).
  - At a level below 0 whose combined query fails (`level` returns None, or
    `ModelFailed`), each frame runs alone; a frame that fails alone is dropped
    into `blocked` with its reason and the others' results are kept. In
    `_descend`, a candidate whose screen fails is skipped the same way. Level 0
    (the side's own SQL) still stops the bucket.
  - `_Bucket.chain() -> list[str]`: one line per path from the side down to
    where it stopped, `"<side> SQL > model_a > model_b: <why>"`, plus each
    blocked model `"<name>: <why>"`. Printed as `Trace <label> chain:` lines
    when a bucket stops or ends with unattributed rows. Model names and reasons
    only.
  - `trace_run(..., ticker: report.Ticker | None = None)` and
    `confirm.run_stored(..., ticker=None)`:
    `ticker.say("sort trace", <label>, wh.spent)` after each level,
    `ticker.say("sort explain", <file name>, wh.spent)` after each explanation
    runs.

- [ ] **Step 1: Write the failing tests** in `T/test_trace.py` (with its
      `FakeWarehouse`):

```python
def test_a_model_whose_query_fails_is_skipped_and_the_others_descend(): ...
    # level 1 has frames A and B; any query holding A's SQL raises
    # resourcesExceeded: B's rows are still attributed, blocked == {"A": "resourcesExceeded"}
def test_a_model_whose_dry_run_fails_is_skipped_not_the_bucket(): ...
def test_a_stopped_bucket_prints_its_model_chain(capsys): ...
    # output has "chain:" and "the dashboard SQL > int_x: resourcesExceeded", no row value
def test_the_trace_descends_up_to_5_levels(): ...
def test_a_cap_still_stops_the_whole_bucket(): ...
```

`T/test_confirm.py`: `test_each_explanation_run_prints_a_progress_line`.

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit**
      `P/trace.py P/confirm.py P/triage.py T/test_trace.py T/test_confirm.py`:
      `feat(cube): the trace skips a model it cannot read and prints where it stopped`
      with body `Refs #6410` and `Refs #6181`.

---

### Task 11: Rows for daily dashboard data: the `latest` reduce rule (#6343)

**Files:**

- Modify: `P/config.py` (`RowSpec.reduce`, `REDUCE_RULES`, `_comparison`),
  `P/pipeline.py` (`dashboard_rows_sql`)
- Test: `T/test_config.py`, `T/test_compare.py` (DuckDB reconcile)

**Interfaces:**

- Consumes: nothing new.
- Produces:
  - YAML:
    `rows: {grain: ..., values: ..., reduce: {rule: latest, by: <dashboard column>}}`.
    `config.REDUCE_RULES = ("latest",)`; `RowSpec.reduce: dict[str, str] = {}`.
    Refused: an unknown `rule` (`"must be one of latest"`), a missing or
    non-identifier `by`, any other key.
  - `pipeline.dashboard_rows_sql`: with `reduce`, the current SELECT becomes a
    subquery that also selects `<by> AS __reduce_by`, wrapped as
    `SELECT * EXCEPT (__reduce_by) FROM (...) QUALIFY RANK() OVER (PARTITION BY <grain dashboard columns> ORDER BY __reduce_by DESC) = 1`.
    The key is the grain; `RANK` keeps tied latest rows, which the reconcile
    then reports as duplicates rather than picking one silently. The WHERE
    (cuts, `dashboard_scope`) applies before the reduce.
  - The fingerprints, `row_population` and the trace read the reduced SQL, as
    for any comparison; no SQL is accepted from YAML.

- [ ] **Step 1: Write the failing tests.**

```python
# T/test_config.py
def test_rows_reduce_takes_latest_and_a_column(tmp_path): ...
@pytest.mark.parametrize("reduce, why", [({"rule": "first", "by": "d"}, "must be one of latest"),
                                         ({"rule": "latest"}, "by"),
                                         ({"rule": "latest", "by": "d; drop"}, "identifier")])
def test_rows_reduce_refuses(tmp_path, reduce, why): ...

# T/test_compare.py (duck)
def test_daily_dashboard_rows_reduce_to_the_latest_per_key_and_match(duck):
    # dashboard: student 1, period Q1, 3 dates, is_chronic 0,0,1; Cube: 1 row is_chronic 1
    # reconcile over dashboard_rows_sql(...) with reduce: only `match`
def test_tied_latest_rows_both_stay(duck): ...
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit**
      `P/config.py P/pipeline.py T/test_config.py T/test_compare.py`:
      `feat(cube): rows.reduce keeps each key's latest dashboard row` with body
      `Refs #6343`.

---

### Task 12: Plainer names and "validation file"

**Files:**

- Modify: `P/cli.py`, `P/config.py`, `P/pipeline.py`, `P/confirm.py`,
  `P/triage.py`, `P/trace.py`, `P/report.py`, `P/answers.py`, `P/preflight.py`,
  `P/discover.py`, `P/describe.py`, `P/checkpoints.py`, `P/latest.py` (messages,
  help, docstrings)
- Test: every `T/test_*.py` whose fixtures or asserted messages use an old name

**Interfaces:**

- Consumes: everything above.
- Produces:
  - Commands: `discover`→`find-field`, `preflight`→`read-sheet`,
    `prove`→`rebuild-sheet`, `run`→`compare`, `triage`→`sort`,
    `triage confirm`→`explain` (a top-level subcommand; the `triage-confirm`
    shim in `main` goes), `add-decisions`→`decide`, `review`→`ask-owner`.
    `record-answers`, `describe`, `reapply`, `members`, `inventory-workbook`,
    `inventory` keep their names. `cli.OLD_COMMANDS: dict[str, str]`; `main`
    refuses an old name (and `triage confirm`) before parsing: stderr
    `"`run`is now`compare`"`, exit 2.
  - YAML keys: `probe`→`sheet_query`, `probe_sql`→`sheet_query_sql`,
    `proof`→`rebuild_check`, `proven_at`→`matched_at`,
    `probe_fingerprint`→`sheet_query_fingerprint`. `Comparison.sheet_query`,
    `sheet_query_sql`, `rebuild_check`; `config.Proof` → `config.RebuildCheck`
    with `matched_at`, `sheet_query_fingerprint`; `config.write_proof` →
    `write_rebuild_check`, writing `rebuild_check:`. The loader refuses each old
    key: `"{path}: comparisons[<i>].probe: renamed; write it as sheet_query"`
    (`proof.proven_at` and `proof.probe_fingerprint` are reached only through
    `proof`, so the `proof` refusal covers them).
  - `pipeline.probe_fingerprint` → `sheet_query_fingerprint`;
    `pipeline.probe_sql` → `sheet_query`. Other Python names (modules,
    `pipeline.run`, `triage.run_triage`, `confirm.Proof`) stay: `pipeline`
    imports the `compare` module, so a `compare` function there would shadow it.
  - Explanations: `confirm.proofs_dir` → `explanations_dir`, path
    `<validation file dir>/explanations/<view>`. When `proofs/<view>` exists and
    `explanations/<view>` does not, `sort` and `explain` refuse:
    `"rename <dir> to <new dir> (git mv); stored explanations moved"`. Every
    message saying "proof" for a stored cause query says "explanation"; the
    answers JSON `reproduce` key `proofs` → `explanations`.
  - "validation file" replaces "view file" in CLI help, refusals and docstrings.
    File names stay `<view>.yml`.
  - Every refusal or print that names a command uses the new name (rg sweep:
    ``rg -n "`(run|prove|triage|triage confirm|add-decisions|review|discover|preflight)\b" P``
    and the same without backticks in f-strings).

Decision: the spec's `probe` / `probe_sql` → `sheet_query` row is split into 2
keys, `sheet_query` (the aggregate) and `sheet_query_sql` (the template), since
the loader must tell them apart and a key holding either would need guessing.

- [ ] **Step 1: Write the failing tests.**

```python
# T/test_cli.py
@pytest.mark.parametrize("old, new", [("discover", "find-field"), ("preflight", "read-sheet"),
    ("prove", "rebuild-sheet"), ("run", "compare"), ("triage", "sort"),
    ("add-decisions", "decide"), ("review", "ask-owner")])
def test_an_old_command_is_refused_with_its_new_name(old, new, capsys):
    assert cli.main([old, "x.yml"]) == 2
    assert f"`{old}` is now `{new}`" in capsys.readouterr().err

def test_triage_confirm_is_refused_as_explain(capsys): ...

# T/test_config.py
@pytest.mark.parametrize("old, new", [("probe", "sheet_query"), ("probe_sql", "sheet_query_sql"),
                                      ("proof", "rebuild_check")])
def test_an_old_key_is_refused_with_its_new_name(tmp_path, old, new): ...

# T/test_confirm.py
def test_an_old_proofs_folder_is_refused_with_its_new_name(tmp_path): ...
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement**, then sweep every test fixture and asserted message
      to the new names
      (`rg -n "probe|proof:|proven_at|\"run\"|\"prove\"|\"triage\"" T`).
- [ ] **Step 4: Run** the whole suite. Expected: all pass, and
      `rg -n "view file" P` returns nothing.
- [ ] **Step 5: Commit** every modified file by name:
      `refactor(cube)!: rename the validator's commands and keys to plain words`.

---

### Task 13: #6181 items 12 and 14 (tableau)

**Files:**

- Modify: `P/tableau.py` (`_nested_under`, `_key_text`, new `export_date`),
  `P/pipeline.py` (`_key`)
- Test: `T/test_tableau.py`, `T/test_cli.py`
  (`test_cell_keys_read_tableau_export_dates_as_the_same_day` keeps passing)

**Interfaces:**

- Produces:
  - `tableau.export_date(text: str) -> date | None`: the date of an M/D/YYYY
    export value, None for anything else (an invalid date included). `_key_text`
    and `pipeline._key` both call it; neither parses M/D/YYYY itself.
  - `_nested_under`: a group whose ops are all `*` nests `ref` into its last
    item that is not measures (`_is_measures`); with none, `ref` crosses in
    front: `_Group([ref, *node.items], ["*"] * len(node.items))`. A group with
    mixed ops raises
    `ValueError("cannot add <ref> to a shelf that mixes / and *; reshape the sheet by hand")`,
    which `set_shelves` already surfaces as a refusal.

- [ ] **Step 1: Write the failing tests.**

```python
def test_set_shelves_nests_into_the_last_dimension_of_a_multi_cross():
    # shelf `A * B * (M1 + M2)`: added C reads `A * (B / C) * (M1 + M2)`
def test_set_shelves_refuses_a_shelf_that_mixes_nest_and_cross(): ...
def test_export_date_reads_m_d_yyyy_only():
    assert tableau.export_date("9/21/2026") == date(2026, 9, 21)
    assert tableau.export_date("13/45/2026") is None
    assert tableau.export_date("2026-09-21") is None
```

- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite.
- [ ] **Step 5: Commit** `P/tableau.py P/pipeline.py T/test_tableau.py`:
      `fix(cube): nest an added shelf field in any all-cross shelf; one export-date helper`
      with body `Refs #6410` and `Refs #6181`.

---

### Task 14: Skills and docs

**Files:**

- Modify: `W/.claude/skills/cube-validation/SKILL.md`,
  `W/.claude/skills/cube-builder/SKILL.md`,
  `W/.claude/skills/cube-validation-answers/SKILL.md`, `W/scripts/CLAUDE.md`
  (the `cube_validation/` row)

Open each with the Read tool. No code changes; no tests. What each edit says:

- `cube-validation`:
  - Intro and _Rules_: the validator compares Cube with dashboards; delete the
    anchors bullets and "consistent only"; proof files path
    `src/cube/validation/explanations/`; "validation file" everywhere.
  - _Running a command_: new names; the credentialed list is `find-field`,
    `rebuild-sheet`, `compare`, `sort`, `explain`; the offline list is
    `ask-owner`, `decide`, `reapply`, `record-answers`, `read-sheet`.
  - Step 3: `sheet_query` / `sheet_query_sql`, `rebuild_check: null`; add
    `rows.reduce: {rule: latest, by: <date column>}` for a dashboard that stores
    daily rows where Cube stores one per period (key = the grain; ties stay and
    show as duplicates).
  - Delete steps 5 (`check-api`) and 6 (`prove --check`); renumber. The
    `compare` step says it checks every confirmed comparison's workbook and Cube
    members, prints the stale and never-run comparisons it will compare
    (`--comparison <id>` repeatable, `--all`), prices every query up front
    ("Compare: N queries, $X (dry run)", refused over `--max-usd` or the daily
    cap), prints a progress line per comparison, and keeps each comparison's
    latest result at its own moment; a new comparison is `rebuild-sheet` then
    `compare --comparison <id>`; changed data alone is not stale.
  - `sort` step: replace the cell-sizing text with coverage (a cell closes when
    every group with a row in it is in `cause` or decided; a comparison whose
    dims sit in the row grain, or without `rows`, cannot be covered and
    `read-sheet` and `compare` name it) and the formula difference
    (`<id>:formula` reaches `cause` on the run's evidence; decide it with
    `formula: true`, usually `domain_owner`, with `definitions:` on the
    comparison). Delete the `--cells` paragraph. Trace: 5 models deep, a model
    it cannot read is skipped with its reason, a stopped bucket prints its model
    chain; progress lines. `sort` names stale or missing comparisons, which
    block `ask-owner`.
  - Delete the "Worked example (DDI)" table and its "Dead ends" paragraph; add
    generic guidance with no DDI names: test each flag of a `where` alone; one
    label (such as a week join) can hide 2 causes; an anchor year (a year a row
    is filed under) can be null.
  - "Filters nothing" bullet rewritten around the #6346 labels and
    `default_call` (`deliberate` for a workbook-only field, `fix_cube` for a gap
    Cube lacks; a candidate member means check, then map under `filters:`).
  - Decisions paragraph: `cells: true` → `formula: true`; `cells:` and old keys
    are refused.
  - _Results_: "validated" means every cell passes and nothing is open; else
    "differs" with its open items; delete the anchor lines.
- `cube-builder`: commands `rebuild-sheet`, `compare` (lines 19-20, 160); delete
  the `check-api` smoke test (line 157) and `prove --check`; step 6 reads
  "`rebuild-sheet`, then `compare`"; step 8 "`compare`"; "validation file".
- `cube-validation-answers`: the reproduce `proofs` entry → `explanations` (line
  87); a question's `moment` is the earliest of its comparisons'.
- `scripts/CLAUDE.md`: the `cube_validation/` row names the new commands
  (`read-sheet`, `rebuild-sheet`, `compare`, `sort`, `explain`, `decide`,
  `ask-owner`).

- [ ] **Step 1: Edit** the 4 files.
- [ ] **Step 2: Check** no old name survives:
      `rg -n "check-api|prove --check|triage confirm|\bprobe\b|proven_at|view file|Worked example|rows\.cell|cells: true|anchors:" .claude/skills/cube-validation .claude/skills/cube-builder .claude/skills/cube-validation-answers scripts/CLAUDE.md`
      → no matches (a "YAML anchor" for `shared:` may stay).
- [ ] **Step 3: Lint** `trunk check --force --no-fix` on the 4 files. Expected:
      no findings.
- [ ] **Step 4: Commit** the 4 files:
      `docs(cube): runbooks for coverage, formula differences and the renamed commands`.

---

## Self-review notes

- Spec coverage: removals §1 → Tasks 1-4; coverage §2 → Tasks 5-6; `run` §3 →
  Task 7; §3a → Task 8; §4 → Tasks 9-10; §5 → Task 11; §5a → Task 12; §6 → Tasks
  13-14 ("validation file" in code: Task 12). Fresh validations and after-merge
  steps are the owner's, not tasks here.
- Not exact, by design: the up-front price stands in for the save script with
  its join; metadata lookups run before the price.
- Between Task 4 and Task 7 no command checks the workbook; between Task 3 and
  Task 5 cells link without exact placement. Both gaps live only inside this
  PR's commits.
