# Validator: Saved Rows and Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `run` and `triage` survive a stop and pick up where they stopped, and
triage reads each comparison's unmatched rows from a saved BigQuery table
instead of rebuilding both sides per proof; plus the #6412 guard, the #6411 cell
confirm, and a proof dry run in `prove --check`.

**Architecture:** `run` compares one comparison at a time, as today. Each
comparison returns its own slice of `_Sides` and saves its unmatched rows to one
labelled table in `teamster-332318.cube_validation_scratch` with the same
multi-statement query that returns the reconcile counts. `run` merges each slice
and writes a checkpoint per comparison into the run folder, which decides what a
resumed `run` skips. `triage` checks each table's labels, prices every proof up
front, runs the proofs one at a time against the saved tables, and records each
finished outcome in `triage-progress.json`. The session temp-table path is
deleted. No threads: see the spec's _Revision 2026-11-13_.

**Tech Stack:** Python 3.13 via `uv run`, `google-cloud-bigquery`, pytest with
DuckDB (`--with duckdb`).

**Spec:**
`docs/superpowers/specs/2026-11-13-validator-saved-rows-resume-design.md`.
Issues #6410 (main), #6411, #6412. PR #6402.

Worktree:
`/workspaces/teamster/.claude/worktrees/cristinabaldor/fix/claude-validator-second-fact-time-dims`
(`W` below). Reach it by absolute path; use `git -C W`. Package:
`W/scripts/cube_validation/` (`P` below). Tests:
`W/tests/scripts/cube_validation/` (`T` below). Run tests from
`/workspaces/teamster` with:

```bash
uv run --project W --with duckdb pytest T/<file>::<test> -q
```

Never bare `pytest` or `python`.

## Global Constraints

- Scratch dataset: `teamster-332318.cube_validation_scratch`, location `US`,
  default table expiration 14 days, read and write for the Data Team group only.
  Named once, in `saved.SCRATCH_DATASET`.
- The owner creates the dataset in their terminal. The implementer never runs
  DDL, DML or any warehouse, Cube or Tableau command outside Task 13.
- The validator creates and replaces tables only inside the scratch dataset.
- One saved table per comparison, with a `bucket` column holding
  `value_differs`, `dims_differ`, `dashboard_only` or `cube_only`.
- Unmatched rows are student-level PII: they stay in BigQuery. Nothing new is
  written locally beyond what `run` writes today (checkpoints hold the same
  aggregates `run.json` holds).
- No worker pools or threads: `run` compares one comparison at a time and
  `triage` runs one proof at a time (spec, _Revision 2026-11-13_).
- Correctness over speed: time is a benchmark only. Never cut or loosen a check,
  guard or refusal to make something faster.
- Resume on its own only when the last checkpoint is under 24 hours old; 24
  hours to 7 days needs `--resume` or `--restart`; over 7 days refuses to
  resume. `--moment` overrides all three.
- The run folder's checkpoint decides what `run` skips; table labels only guard
  `triage` (a mismatch refuses, never reads).
- Every query counts against `--max-usd` and `--max-usd-per-day` through
  `Warehouse`. `--max-usd` caps each process; `run.json`'s `cost_usd` is the
  total across processes.
- Docstrings follow `W/src/teamster/CLAUDE.md`; comments follow
  `.claude/rules/comments.md` (no measurements, no history).
- Commits: conventional commits, files staged by name, message ending with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Each fix of the
  first three tasks is its own commit.

## Review Focus

1. A resumed run merges saved slices and fresh ones in a different order from an
   uninterrupted one: `cells` and `groups` reorder and `run.json` differs.
   Expected: merged in config order, identical `run.json` but `cost_usd`. Pinned
   in Task 9 (`test_a_stopped_run_resumes_to_the_same_result`).
2. A checkpoint under 24 hours old whose build has aged past time travel (the
   build start older than 7 days less the 1-hour margin). Expected: a refusal
   naming `--restart`, not a BigQuery error mid-run. Pinned in Task 9
   (`test_a_resume_past_time_travel_refuses_before_any_query`).
3. A comparison fails partway (a cap, a refusal). Expected: every comparison
   before it is checkpointed, the failed one is not, and its table (if the
   script got that far) is replaced on resume. Pinned in Task 9
   (`test_a_stopped_run_resumes_to_the_same_result`, first half).
4. A stopped run's spend is lost from `run.json`. Expected: `cost_usd` adds
   every process's spend from `run-state.json`. Pinned in Task 9 (the
   `total_spend` assertion) and Task 8 (`test_spend_adds_up_across_processes`).
5. A table with the right name holding another run's rows (same view, moment and
   comparison, but a `--fact-dataset` dev run or an edited comparison).
   Expected: triage refuses that comparison's proofs. Pinned in Task 10
   (`test_a_proof_refuses_saved_rows_labelled_for_another_run`).

---

## Findings from the code that shape the plan

- The trace does not need session temp tables. `trace.py` never calls
  `Warehouse.session` or `Warehouse.freeze`; `MAX_QUERY_CHARS` (`trace.py:64`)
  batches the trace's own queries (`trace.py:525-544`, `603`, `716`, `922`).
  Only `confirm.run_proof` switches on it (`confirm.py:1074`), and
  `Prepared.frozen` (`trace.py:985`) exists only for that switch. Task 10
  deletes `Warehouse.session`, `Warehouse.freeze`, `_session_settings`,
  `_SESSION_REF`, `confirm._freeze`, `confirm.frozen_sql` and `Prepared.frozen`;
  `MAX_QUERY_CHARS` stays for the trace.
- `_Sides` (`pipeline.py:712-732`) also holds `cube_tables` and `live`, which
  the spec's checkpoint list omits. Both go in the checkpoint, or a resumed
  run's `changed_dims` (`pipeline.py:1402`) and `live_sources` differ.
  `_Sides.clauses` is never read or written; Task 7 deletes it.
- The tables only the Cube side reads already come from `Prepared.row_sides`
  (`sides.cube.tables - sides.dashboard.tables`, `confirm.py:1062`), which
  triage rebuilds for its compile-only check anyway. The plan does not save them
  a second time.
- `frozen_sql`'s `joined` (`confirm.py:711`) differs from the reconcile's
  (`compare.py:218`): keys and per-side grain versus `moved` and cut flags. The
  saved table needs both, so the save query builds one `joined` with
  `keys=True, moved=True` and both sides' grain (`__gc<i>`, `__gd<i>`), since
  the side holding a row differs by bucket and the 2 sides can type a grain
  column differently.
- `cut_flags` (`pipeline.py:225-228`) returns None when a cut caption is not a
  row column, which is why the DDI `mastery-bucket-*` cells cannot be sized.
  `scope` needs nothing: both row queries already apply it
  (`pipeline.py:285-286`, `336-338`).
- The DDI `students-bucket-*` comparisons measure `count_students` (a distinct
  count, `decimals: 0`), not a share; `confirm._rebuilt` sizes them as the mean
  of `is_mastery`. Task 2 adds a distinct-student count cell kind.
- `report.save_local` names the folder after `moment.end` (`report.py:412-416`),
  so a re-run of a finished moment shares its folder. A run-state file marks a
  folder unfinished instead of the absence of `run.json`.

## File Structure

```text
P/saved.py         new: scratch dataset constant, table id, labels
P/checkpoints.py   new: run folder state and per-comparison checkpoints
P/progress.py      new: triage-progress.json
P/bq.py            script, saved_labels; session path removed
P/compare.py       reconcile_script, unmatched_rows_sql, cell_students_sql
P/pipeline.py      slices, side_fingerprints, resume
P/confirm.py       identifier guard, cell kinds, saved-table proofs, check_proofs
P/trace.py         Prepared.frozen removed
P/triage.py        --comparison, progress
P/config.py        rows.cell
P/report.py        run_dir, RunResult.cell_students
P/cli.py           run --resume/--restart, triage --comparison, prove --check
```

---

### Task 1: The identifying-column guard lets category numbers pass (#6412)

**Files:**

- Modify: `P/confirm.py:295-307` (`_identifies`)
- Test: `T/test_confirm.py` (beside
  `test_check_sql_refuses_a_literal_on_a_column_that_names_a_person`, line 560)

**Interfaces:**

- Consumes: nothing new.
- Produces: `_identifies(column: str, student: set[str]) -> bool`, unchanged
  signature. `_id_like` (what a cause may not select) keeps `_ID_SUFFIXES`
  unchanged.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize(
    "where",
    ["r.performance_band_label_number = 3", "r.module_number = 2",
     "r.grade_level_number IN (5, 6)"],
)  # fmt: skip
def test_check_sql_lets_a_literal_meet_a_category_number(where):
    assert confirm.check_sql(
        f"SELECT u.__row, CASE WHEN {where} THEN 'C1' "
        "ELSE 'UNEXPLAINED' END AS cause FROM {unmatched} AS u "
        "LEFT JOIN `teamster-332318`.`ds`.`r` AS r ON r.student = u.lea",
        GRAIN,
        STUDENT,
    ) == {"C1", "UNEXPLAINED"}
```

Add to the existing refusal parametrize list: `"r.student_number = 7"`,
`"r.employee_number = 7"`, `"r.state_studentnumber = 7"`,
`"r.lea_student_identifier = 7"`, `"r.teacher_number = 7"`,
`"r.home_phone_number = 7"`, `"r.guardian_phone_number = 7"`. Keep the existing
five (`r.staff_number = 7` must still refuse).

- [ ] **Step 2: Run to fail**

Run: `... pytest T/test_confirm.py -k "category_number or names_a_person" -q`
Expected: the 3 category-number cases FAIL with "identifying column with a
literal"; the refusal cases pass already except `lea_student_identifier`.

- [ ] **Step 3: Implement in `P/confirm.py`**

Add, above `_identifies`:

```python
# Numbers that name or reach a person (direct identifiers and contact details in
# `.claude/rules/ferpa-pii.md`); any other `_number` column numbers a category,
# such as a band or a module.
_PERSON_NUMBERS = ("student_number", "studentnumber", "employee_number",
                   "phone_number", "state_id", "local_id",
                   "school_specific_id")  # fmt: skip
_PEOPLE = ("student", "employee", "staff", "teacher")
```

`_identifies` returns True when: `name in student`; or
`name.endswith(("_name", "_email"))`; or `name.endswith(_PERSON_NUMBERS)`; or a
`_PEOPLE` word is in `name` and
`name.endswith(("_id", "_key", "_number", "_identifier"))`. Update its docstring
to say a category number passes and a person's number does not.

- [ ] **Step 4: Run to pass**

Run: `... pytest T/test_confirm.py -q` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git -C W add scripts/cube_validation/confirm.py tests/scripts/cube_validation/test_confirm.py
git -C W commit -m "fix(cube): let a proof compare a category number with a literal" \
  -m "Refs #6412" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Cells confirm on bucket comparisons (#6411)

Two causes, one commit: the cut captions the cells vary by become row columns,
so the run keeps sums per cut; and a comparison can declare its cell a count of
distinct students, sized from per-cell student counts.

**Files:**

- Modify: `P/pipeline.py:204-243` (`cut_flags`), `268-272` (`_row_pairs`),
  `754-878` (`_compare_one`: one more query), `711-732` (`_Sides.cell_students`)
- Modify: `P/config.py:91-98` (`RowSpec.cell`), `372-382` (read `rows.cell`)
- Modify: `P/compare.py` (new `cell_students_sql`)
- Modify: `P/report.py:78-117` (`RunResult.cell_students`),
  `P/pipeline.py:1527-1577` (`_run_from_json`)
- Modify: `P/confirm.py:1280-1340` (`_sizable`, new `_students_rebuilt`),
  `1343-1507` (`link_cells`)
- Test: `T/test_confirm.py`, `T/test_compare.py`, `T/test_config.py`

**Interfaces:**

- Produces:
  - `pipeline._varying_captions(comparison: Comparison) -> list[str]` (the
    captions whose value differs across cuts; `cut_flags` uses it).
  - `RowSpec.cell: str = "mean"`;
    `config.ROW_CELLS = ("mean", "count_students")`.
  - `compare.cell_students_sql(cube_rows_sql: str, dashboard_rows_sql: str, rows: RowSpec, group_by: list[ColumnPair], filters: Sequence[tuple[str, str]] = (), cuts: Sequence[tuple[str, str]] = ()) -> str`
    returning `side` (`c`/`d`), `__cut` (cut index; 0 when `cuts` is empty),
    each group-by column by its Cube name (the dashboard's cell for a `d` row),
    and `n_students` (distinct first-grain values).
  - `RunResult.cell_students: dict[str, list[dict]]`, per comparison
    `{"side", "cut", "dims": [[column, value], ...], "n"}`.
  - `_Sides.cell_students: dict[str, list[dict]]`.

- [ ] **Step 1: Write the failing tests**

In `T/test_confirm.py`, replace
`test_cut_flags_need_each_varying_caption_among_the_row_columns` (line 1521)
with:

```python
def test_a_varying_cut_caption_becomes_a_row_column_on_both_sides():
    from dataclasses import replace

    by_region = replace(BY_TYPE, cuts=[{"Region": "A"}, {"Region": "B"}],
                        filters={**BY_TYPE.filters, "Region": ColumnPair("region", "region")})  # fmt: skip

    flags = pipeline.cut_flags(by_region)

    assert [label for label, _, _ in flags] == ['{"Region": "A"}', '{"Region": "B"}']
    assert "c.region" in flags[1][1] and "d.region" in flags[1][2]
    assert ColumnPair("region", "region") in pipeline._row_pairs(by_region)
    # A caption every cut shares stays out of the rows.
    assert ColumnPair("year", "year") not in pipeline._row_pairs(by_region)
```

Add, after `_rate_run`:

```python
STUDENTS = replace(RATE, measure="count_students", decimals=0,
                   rows=replace(RATE.rows, cell="count_students"))  # fmt: skip
CELL_X = [{"side": "c", "cut": "{}", "dims": [["abbreviation", "X"]], "n": 5},
          {"side": "d", "cut": "{}", "dims": [["abbreviation", "X"]], "n": 3}]  # fmt: skip


def _students_run(cube, dashboard, students=CELL_X):
    return replace(_rate_run(cube, dashboard), cell_students={"mastery": students})


def test_a_student_count_cell_links_when_its_students_rebuild_both_sides(tmp_path, monkeypatch):
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[STUDENTS])
    cells = _cells(tmp_path, monkeypatch, run=_students_run(5.0, 3.0), cfg=cfg)
    assert cells["suggestion"] == "cause"


def test_a_student_count_cell_its_students_do_not_rebuild_stays_open(tmp_path, monkeypatch, capsys):
    cfg = ViewConfig(view="v", fact="m.fct", comparisons=[STUDENTS])
    with pytest.raises(pipeline.Refusal, match="1 of 1 differing cells"):
        _cells(tmp_path, monkeypatch, run=_students_run(6.0, 3.0), cfg=cfg)
    assert "rebuilt Cube 5, dashboard 3" in capsys.readouterr().out
```

(`replace` is `dataclasses.replace`; import it at module top if not there.)

In `T/test_compare.py`:

```python
def test_cell_students_count_each_student_once_per_side_and_cell(duck):
    duck.table("c_rows", "lea BIGINT, aid VARCHAR, school VARCHAR",
               [(1, "a", "X"), (1, "b", "X"), (2, "c", "X")])
    duck.table("d_rows", "student BIGINT, item VARCHAR, school VARCHAR",
               [(1, "a", "X"), (3, "d", "Y")])  # fmt: skip
    rows = RowSpec(grain=[ColumnPair("student", "lea"), ColumnPair("item", "aid")], values=[])
    got = duck.rows(compare.cell_students_sql(
        "SELECT lea, aid, school FROM c_rows", "SELECT student, item, school FROM d_rows",
        rows, [ColumnPair("school", "school")]))  # fmt: skip
    assert sorted((r["side"], r["__cut"], r["school"], r["n_students"]) for r in got) == [
        ("c", 0, "X", 2), ("d", 0, "X", 1), ("d", 0, "Y", 1)]
```

In `T/test_config.py`: a view file with `rows: {..., cell: share}` refuses with
a message naming `rows.cell` and `count_students`; `cell: count_students` loads.

- [ ] **Step 2: Run to fail**

Run: `... pytest T/test_confirm.py T/test_compare.py T/test_config.py -q`
Expected: FAIL (`cut_flags` returns None; `RowSpec` has no `cell`; `compare` has
no `cell_students_sql`).

- [ ] **Step 3: Implement**

- `pipeline._varying_captions`: the `varying` list now inline in `cut_flags`.
  `_row_pairs` appends `comparison.filters[c]` for each varying caption not
  already among its pairs, so `row_query`, `dashboard_rows_sql`,
  `RowSides.columns` and `cut_flags` all see them. `cut_flags` then returns None
  only without `rows`; update its docstring.
- `RowSpec.cell` and its reader (`rows_reader.get("cell", str, default="mean")`,
  `reader.fail` outside `ROW_CELLS`).
- `compare.cell_students_sql`: built on `_joined` (with `extra` holding the cut
  flags as in `reconcile_sql`, and each group-by column's dashboard label as
  `__dl_<cube name>`); one `UNION ALL` branch per side and cut: Cube rows
  (`__cin IS NOT NULL`, its cut flag) grouped by the group columns, dashboard
  rows (`__din IS NOT NULL`, `__dkeep` when filters, its cut flag) grouped by
  `__dl_` columns renamed to the Cube names.
- `_compare_one`: for `comparison.rows.cell == "count_students"` with cut flags
  or a single cut, run `cell_students_sql` (as `reconcile_sql`'s arguments) and
  store `sides.cell_students[comparison.id]` as the `RunResult` shape, the cut
  index mapped to its label. `run` copies `sides.cell_students` into
  `RunResult`; `_run_from_json` reads `data.get("cell_students", {})`.
- `confirm._students_rebuilt(students: list[dict], cell: dict) -> tuple[float | None, float | None]`:
  per side, the `n` of the entry whose cut equals `cell["cut"]` and whose dims
  equal the cell's dims (None when absent). In `link_cells`, a comparison with
  `rows.cell == "count_students"` takes that branch in place of the rate branch:
  no entries for the comparison is "cannot be sized"; a side that does not pass
  `compare.cell_verdict` is "does not rebuild from its rows" with the rebuilt
  values, as the rate branch words it.

- [ ] **Step 4: Run to pass**

Run: `... pytest T/ -q` (the whole cube_validation folder; existing tests of
`run` SQL must hold). Expected: PASS.

- [ ] **Step 5: Commit**

Stage the 5 source files and 3 test files by name.
`fix(cube): confirm cells on bucket comparisons from per-cut sums and student counts`,
body `Refs #6411`, then the Co-Authored-By line.

---

### Task 3: `prove --check` dry-runs every stored proof (#6410)

**Files:**

- Modify: `P/confirm.py` (new `check_proofs`), `P/pipeline.py` (new
  `current_row_sides`), `P/cli.py:526-530`
- Test: `T/test_confirm.py`, `T/test_cli.py`

**Interfaces:**

- Produces:
  - `pipeline.current_row_sides(cfg: ViewConfig, comparison: Comparison, *, cube: Cube, schools: set[str]) -> RowSides`:
    the row SQL on today's tables, no time travel
    (`AsOf(sql, frozenset(), frozenset())`).
  - `confirm.check_proofs(cfg: ViewConfig, directory: Path, *, wh: Warehouse, cube: Cube) -> list[str]`:
    one line per stored proof that fails `read_proof`, names no comparison of
    `cfg`, fails `check_sql`, or that BigQuery rejects on a dry run
    (`f"{path.name}: BigQuery rejects it ({bigquery_said(exc)})"`). Dry runs are
    free and cap nothing (`wh.estimate`).

- [ ] **Step 1: Write the failing tests**

```python
def test_check_proofs_lists_a_proof_bigquery_rejects(tmp_path, offline, monkeypatch):
    monkeypatch.setattr(pipeline, "current_row_sides", lambda *a, **k: SIDES)
    directory, path = _proof(tmp_path)

    class Rejecting(Wh):
        def estimate(self, sql):
            raise BadRequest("Unrecognized name: missing_col",
                             errors=[{"reason": "invalidQuery"}])  # fmt: skip

    assert confirm.check_proofs(CFG, directory, wh=Rejecting(None), cube=None) == [
        f"{path.name}: BigQuery rejects it (job ?, invalidQuery: Unrecognized name: missing_col)"
    ]


def test_check_proofs_dry_runs_the_proof_on_today_s_tables(tmp_path, offline, monkeypatch):
    monkeypatch.setattr(pipeline, "current_row_sides", lambda *a, **k: SIDES)
    directory, _ = _proof(tmp_path)
    seen = []

    class Recording(Wh):
        def estimate(self, sql):
            seen.append(sql)
            return 0.0

    assert confirm.check_proofs(CFG, directory, wh=Recording(None), cube=None) == []
    (sql,) = seen
    assert "{unmatched}" not in sql and "FOR SYSTEM_TIME" not in sql
```

In `T/test_cli.py`: `prove --check` with a stored proof file under
`tmp_path / "proofs" / "v"` and `confirm.check_proofs` monkeypatched to return
`["x.sql: BigQuery rejects it (...)"]` prints that line and returns 0.

- [ ] **Step 2: Run to fail**

Expected: FAIL, `confirm` has no `check_proofs`.

- [ ] **Step 3: Implement**

`check_proofs` builds
`proof_query(*unmatched_sql(cfg, comparison, sides, proof.bucket, [], None), proof.body, literals)`
from `current_row_sides` (network schools fetched once). Task 10 swaps the
inline rows for `pipeline.inline_unmatched`. In `cli.py`, the `--check` branch
also calls
`confirm.check_proofs(cfg, confirm.proofs_dir(args.view, cfg.view), wh=_warehouse(args), cube=cube)`
with the same `cube` it passes `prove_check`, prints "Proofs BigQuery rejects:"
and the lines when any, and still returns 0.

- [ ] **Step 4: Run to pass**

Run: `... pytest T/test_confirm.py T/test_cli.py -q` — PASS.

- [ ] **Step 5: Commit**

`feat(cube): dry-run every stored proof in prove --check`, body `Refs #6410`.

---

### Task 4: The scratch dataset and saved-table names

**Files:**

- Create: `P/saved.py`, `T/test_saved.py`

**Interfaces:**

- Produces:
  - `SCRATCH_DATASET = "cube_validation_scratch"`, `SAVED_DAYS = 14`,
    `SAVED_BUCKETS = ("value_differs", "dims_differ", "dashboard_only", "cube_only")`.
  - `table_id(view: str, build: Build, comparison_id: str) -> str`: dotted id
    `teamster-332318.cube_validation_scratch.<name>`, where `<name>` is
    `f"{view}__{stamp}__{comparison_id}"` lowercased with every character
    outside `[a-z0-9_]` turned to `_`, then `_` and the first 8 hex of
    `sha256(comparison_id)`; `stamp` is `report.save_local`'s folder stamp.
  - `table_sql(table_id: str) -> str`: each part in its own backticks.
  - `labels(view: str, build: Build, comparison_id: str, fingerprint: str) -> dict[str, str]`:
    keys `view`, `moment`, `comparison`, `fingerprint`; values lowercased,
    characters outside `[a-z0-9_-]` to `_`, cut at 63; `fingerprint` is its
    first 32 hex.

- [ ] **Step 1: HANDOFF to the owner (do not run)**

Ask the owner to run, in their terminal:

```sql
CREATE SCHEMA `teamster-332318.cube_validation_scratch`
OPTIONS (
  location = 'US',
  default_table_expiration_days = 14,
  description = 'Cube validator: each run''s unmatched rows per comparison. Student-level; Data Team only.'
);
```

A new dataset grants the project's readers, writers and owners by default. To
limit it to the Data Team group:

```bash
bq show --format=prettyjson teamster-332318:cube_validation_scratch > ~/scratch_acl.json
# In "access": keep the OWNER entries; replace every READER and WRITER entry with
#   {"role": "WRITER", "groupByEmail": "<the Data Team group's address>"}
bq update --source ~/scratch_acl.json teamster-332318:cube_validation_scratch
bq show --format=prettyjson teamster-332318:cube_validation_scratch
```

A project-level BigQuery data role still reads every dataset; the owner checks
who holds one (`gcloud projects get-iam-policy teamster-332318`). Wait for the
owner's "done" before Task 13; Tasks 5 to 12 run offline and do not wait.

- [ ] **Step 2: Write the failing tests** (`T/test_saved.py`)

```python
END = datetime(2026, 10, 28, 21, 35, tzinfo=timezone.utc)
BUILD = Build(END - timedelta(minutes=1), END, "job")


def test_a_table_is_named_by_view_moment_and_comparison():
    sha = hashlib.sha256(b"ada-region").hexdigest()[:8]
    assert saved.table_id("v", BUILD, "ada-region") == (
        f"teamster-332318.cube_validation_scratch.v__2026_10_28t213500z__ada_region_{sha}")
    assert saved.table_sql(saved.table_id("v", BUILD, "ada-region")).startswith(
        "`teamster-332318`.`cube_validation_scratch`.`v__")


def test_ids_that_differ_only_in_punctuation_get_different_tables():
    assert saved.table_id("v", BUILD, "a-b") != saved.table_id("v", BUILD, "a_b")


def test_labels_are_what_bigquery_takes():
    got = saved.labels("v", BUILD, "Ada Region", "f" * 64)
    assert got == {"view": "v", "moment": "2026-10-28t213500z",
                   "comparison": "ada_region", "fingerprint": "f" * 32}  # fmt: skip
```

- [ ] **Step 3: Run to fail** — FAIL, no module `saved`.

- [ ] **Step 4: Implement `P/saved.py`** — pure functions, no BigQuery import.
      Take the stamp from a new `report.run_stamp(moment: Build) -> str`, which
      `report.save_local` uses too (`report.py:412-415`).

- [ ] **Step 5: Run to pass; commit**

`feat(cube): name each comparison's saved-rows table and its labels`, body
`Refs #6410`. Stage `saved.py`, `report.py`, `test_saved.py`.

---

### Task 5: `Warehouse` runs a script and reads a saved table's labels

**Files:**

- Modify: `P/bq.py` (new methods, module docstring)
- Test: `T/test_bq.py`

**Interfaces:**

- Produces:
  - `Warehouse.script(statements: list[str], timeout_s: float | None = None) -> list[dict]`:
    runs the statements as one multi-statement query (`";\n".join`) through
    `rows`, returning the last statement's rows and billing the whole job.
  - `Warehouse.saved_labels(table_id: str) -> dict[str, str] | None`: the
    table's labels, or None when `get_table` raises `NotFound`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_script_runs_as_one_job_and_returns_its_last_rows():
    client = FakeClient(rows=[{"n": 2}])
    assert Warehouse(client=client).script(["CREATE TEMP TABLE a AS SELECT 1", "SELECT 2 AS n"]) == [{"n": 2}]
    assert client.queries == [("CREATE TEMP TABLE a AS SELECT 1;\nSELECT 2 AS n", False)]


def test_saved_labels_read_a_table_and_none_for_a_missing_one():
    assert Warehouse(client=FakeClient(SimpleNamespace(labels={"view": "v"}))).saved_labels("p.d.t") == {"view": "v"}

    class Gone(FakeClient):
        def get_table(self, ref):
            raise NotFound(ref)

    assert Warehouse(client=Gone()).saved_labels("p.d.t") is None
```

- [ ] **Step 2: Run to fail** — both fail on missing methods.

- [ ] **Step 3: Implement** as the Interfaces say. Update the module docstring
      ("Only SELECTs, dry runs and the validator's saved tables in
      `saved.SCRATCH_DATASET` are issued").

- [ ] **Step 4: Run to pass; commit** —
      `feat(cube): run a multi-statement script and read a saved table's labels`,
      `Refs #6410`.

---

### Task 6: The save query: unmatched rows saved once, counts from the same job

**Files:**

- Modify: `P/compare.py:169-388` (`reconcile_sql`, `_joined`; new functions)
- Test: `T/test_compare.py`

**Interfaces:**

- Consumes: `saved.SAVED_BUCKETS`, `saved.SAVED_DAYS`.
- Produces:
  - `compare.reconcile_script(cube_rows_sql: str, dashboard_rows_sql: str, rows: RowSpec, group_by: list[ColumnPair], filters: Sequence[tuple[str, str]] = (), cuts: Sequence[tuple[str, str]] = (), *, table: str, labels: dict[str, str] | None = None, expire_days: int | None = None) -> list[str]`:
    3 statements. (1) `CREATE TEMP TABLE __joined AS` the `c`, `d` and `joined`
    CTEs built with `keys=True, moved=True`, the reconcile's cut flags and
    `__dkeep`, and each grain column from both sides (`__gc<i>`, `__gd<i>`). (2)
    `CREATE OR REPLACE TABLE {table}` with `OPTIONS(...)` when `labels` or
    `expire_days` is given, as
    `SELECT bucket, __row, <group-by Cube names>, __d_<each>, __gc<i>, __gd<i>, __rn, __ck<j>, __dk<j> FROM __joined WHERE bucket IN SAVED_BUCKETS`.
    `__row` is `FARM_FINGERPRINT(TO_JSON_STRING(STRUCT(__k0, ..., __rn)))`. (3)
    the reconcile's outer `SELECT ... GROUP BY` over `__joined`, keeping its
    `-- outer` marker.
  - `compare.unmatched_rows_sql(...same positional args...) -> str`: one query
    returning statement (2)'s rows inline
    (`WITH ... SELECT ... FROM joined WHERE ...`), for a dry run with no saved
    table.
  - `reconcile_sql` keeps its result; the 3 builders share private helpers for
    `joined`'s extras, the saved columns and the outer select.

- [ ] **Step 1: Write the failing tests**

```python
ROWS_V = RowSpec(grain=[ColumnPair("student", "lea"), ColumnPair("item", "aid")],
                 values=[ColumnPair("v", "v")])  # fmt: skip
SAVE_ARGS = ("SELECT lea, aid, school, v FROM c_rows",
             "SELECT student, item, school, v FROM d_rows",
             ROWS_V, [ColumnPair("school", "school")])  # fmt: skip


def _save_tables(duck):
    # The 2 sides type the student differently: BigQuery reads each side's own.
    duck.table("c_rows", "lea BIGINT, aid VARCHAR, school VARCHAR, v DOUBLE",
               [(1, "a", "X", 1.0), (2, "b", "X", 0.0), (3, "c", "Y", 1.0)])
    duck.table("d_rows", "student VARCHAR, item VARCHAR, school VARCHAR, v DOUBLE",
               [("1", "a", "X", 1.0), ("2", "b", "X", 1.0), ("4", "d", "Y", 0.0)])  # fmt: skip


def test_the_save_script_counts_exactly_as_the_reconcile(duck):
    _save_tables(duck)
    *setup, counts = compare.reconcile_script(
        *SAVE_ARGS, table="`teamster-332318`.`cube_validation_scratch`.`saved_t`")
    for statement in setup:
        duck.rows(statement)
    assert duck.rows(counts) == duck.rows(compare.reconcile_sql(*SAVE_ARGS))


def test_the_save_script_keeps_only_unmatched_rows_with_each_side_s_grain(duck):
    _save_tables(duck)
    for statement in compare.reconcile_script(*SAVE_ARGS, table="saved_t")[:2]:
        duck.rows(statement)
    assert duck.rows("SELECT bucket, school, __gc0, __gd0 FROM saved_t ORDER BY bucket") == [
        {"bucket": "cube_only", "school": "Y", "__gc0": 3, "__gd0": None},
        {"bucket": "dashboard_only", "school": "Y", "__gc0": None, "__gd0": "4"},
        {"bucket": "value_differs", "school": "X", "__gc0": 2, "__gd0": "2"},
    ]


def test_the_saved_table_carries_its_labels_and_expiry():
    create = compare.reconcile_script(*SAVE_ARGS, table="`p`.`d`.`t`",
                                      labels={"view": "v", "fingerprint": "ab"},
                                      expire_days=14)[1]  # fmt: skip
    assert create.startswith("CREATE OR REPLACE TABLE `p`.`d`.`t`\nOPTIONS(")
    assert "labels = [('fingerprint', 'ab'), ('view', 'v')]" in create
    assert "expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)" in create


def test_unmatched_rows_inline_are_the_saved_rows(duck):
    _save_tables(duck)
    for statement in compare.reconcile_script(*SAVE_ARGS, table="saved_t")[:2]:
        duck.rows(statement)
    inline = duck.rows(f"SELECT * FROM ({compare.unmatched_rows_sql(*SAVE_ARGS)}) ORDER BY __row")
    assert inline == duck.rows("SELECT * FROM saved_t ORDER BY __row")
```

- [ ] **Step 2: Run to fail** — FAIL, no `reconcile_script`.

- [ ] **Step 3: Implement.** The moved-row `__d_<column>` from `moved=True`
      replaces `frozen_sql`'s; every reader of `__d_` (an item's `d:` dims,
      `StudentCount.moved`) reads a `dims_differ` row only, where the 2 agree.

- [ ] **Step 4: Run to pass** — `... pytest T/test_compare.py -q`.

- [ ] **Step 5: Commit** —
      `feat(cube): save a comparison's unmatched rows in the reconcile's own query`,
      `Refs #6410`.

---

### Task 7: Each comparison yields its own slice and saves its table

**Files:**

- Modify: `P/pipeline.py:711-732` (`_Sides`), `735-878` (`_compare_one`),
  `896-971` (`row_sides`)
- Test: `T/test_cli.py`, new `T/test_pipeline_slices.py`

**Interfaces:**

- Consumes: `compare.reconcile_script`, `compare.unmatched_rows_sql`,
  `saved.table_id`, `saved.table_sql`, `saved.labels`, `saved.SAVED_DAYS`,
  `Warehouse.script`.
- Produces:
  - `_Sides.merge(self, other: "_Sides") -> None`: unions sets and `moved`,
    extends `cells` and `groups`, updates every dict.
  - `_Sides.to_json(self) -> dict` and
    `_Sides.from_json(data: dict) -> "_Sides"`: lossless round trip (tuples in
    `Group.dims`, `Group.nulls`, `Cell.dims`, `sql`, and the `students` keys
    come back as tuples).
  - `side_fingerprints(cfg: ViewConfig, comparison: Comparison, *, wh: Warehouse, cube: Cube, build: Build, schools: set[str]) -> dict[str, str]`:
    the `cube` and `dashboard` fingerprints `_compare_one` records today, from
    compiled and as-of SQL only, no query run. `_compare_one` and `row_sides`
    both call it (one shared compile and as-of cache object, `_Expand`, holding
    today's `cube_sql` and `at` closures).
  - `checkpoint_fingerprint(comparison: Comparison, fingerprints: dict[str, str]) -> str`:
    `sha256(json.dumps([dataclasses.asdict(comparison), fingerprints], sort_keys=True, default=str))`.
  - `save_script(cfg: ViewConfig, comparison: Comparison, sides: RowSides, table: str, labels: dict[str, str] | None) -> list[str]`
    and
    `inline_unmatched(cfg: ViewConfig, comparison: Comparison, sides: RowSides) -> str`:
    `reconcile_script` / `unmatched_rows_sql` with the arguments `_compare_one`
    passes `reconcile_sql` today (`wrap_cube` of `sides.cube_rows_sql`,
    `sides.dashboard.sql`, `group_dims`, `_filter_flags`, the cut flag pairs).
  - `_compare_one(cfg, comparison, *, wh, cube, build, schools, moved: dict[str, bool]) -> _Sides`:
    returns the comparison's slice instead of mutating a shared one. It reads
    `moved` and returns, in `slice.moved`, every table it knows the answer for.
    Order: fingerprints, cells, then the rows: `wh.script(save_script(...))` to
    `saved.table_id(cfg.view, build, comparison.id)` labelled with
    `checkpoint_fingerprint`, expiring after `SAVED_DAYS`; then students and
    cell students.
  - `_Sides.clauses` deleted.

- [ ] **Step 1: Write the failing tests**

`T/test_pipeline_slices.py`:

```python
def test_a_comparison_slice_survives_json():
    s = pipeline._Sides(
        cube_tables={"m.fct"}, live={"g.sheet"},
        cells=[pipeline.Cell("c", "{}", "X", 1.0, 2.0, "differs", (("school", "X"),))],
        groups=[Group("c", (("school", ""),), "cube_only", 3, 2, ("school",))],
        sql={"c": ("SELECT d", "SELECT c")},
        fingerprints={"c": {"cube": "1", "dashboard": "2"}}, moved={"m.dim": False},
        cell_sql={"c": {"{}": ["d", "c"]}}, cell_sql_usd={"c": {"{}": [0.1, 0.2]}},
        cell_rows={"c": [{"bucket": "match"}]}, students={"c": {("{}", ("X",)): 12}},
        cell_students={"c": [{"side": "c", "cut": "{}", "dims": [["school", "X"]], "n": 5}]},
    )  # fmt: skip
    assert pipeline._Sides.from_json(json.loads(json.dumps(s.to_json()))) == s


def test_a_changed_comparison_entry_changes_its_checkpoint_fingerprint():
    a = Comparison(id="c", measure="m", decimals=2)
    fp = {"cube": "1", "dashboard": "2"}
    assert pipeline.checkpoint_fingerprint(a, fp) == pipeline.checkpoint_fingerprint(a, dict(fp))
    assert pipeline.checkpoint_fingerprint(a, fp) != pipeline.checkpoint_fingerprint(replace(a, decimals=3), fp)
    assert pipeline.checkpoint_fingerprint(a, fp) != pipeline.checkpoint_fingerprint(a, {**fp, "cube": "9"})
```

`T/test_cli.py`:

```python
def test_run_saves_each_comparison_s_unmatched_rows_to_a_labelled_table(fakes, tmp_path):
    assert cli.main(["run", str(_file(tmp_path))]) == 0
    script = _reconcile(fakes.bq)
    sha = hashlib.sha256(b"ada-region").hexdigest()[:8]
    assert "CREATE TEMP TABLE __joined" in script
    assert ("CREATE OR REPLACE TABLE `teamster-332318`.`cube_validation_scratch`."
            f"`v__2026_10_22t204400z__ada_region_{sha}`") in script  # fmt: skip
    assert "('comparison', 'ada-region')" in script
```

- [ ] **Step 2: Run to fail** — FAIL (`_Sides` has no `to_json`; no saved table
      in the script).

- [ ] **Step 3: Implement** as the Interfaces say. `run` keeps a single
      sequential loop, merging each returned slice into its `_Sides` (Task 9
      adds checkpoints and resume). `row_sides` compares
      `side_fingerprints(...)` with the run's and keeps its refusal text.

- [ ] **Step 4: Run to pass** — `... pytest T/ -q` (every existing `run`,
      `triage` and trace test must pass). `test_cli.py`'s `_reconcile(bq)` now
      returns the whole 3-statement script; it still holds `-- outer` and every
      clause the old query held, so its readers need no change unless one
      assumes the text starts with `WITH`.

- [ ] **Step 5: Commit** —
      `feat(cube): compare each comparison into its own slice and save its rows`,
      `Refs #6410`.

---

### Task 8: Run folder state and checkpoints

**Files:**

- Create: `P/checkpoints.py`, `T/test_checkpoints.py`
- Modify: `P/report.py:401-419` (`run_dir`)

**Interfaces:**

- Produces:
  - `report.run_dir(root: Path, view: str, moment: Build) -> Path` (`save_local`
    writes into it).
  - In `checkpoints.py` (file I/O only, no BigQuery, no `pipeline` import):
    - `STATE = "run-state.json"`, `DIR = "checkpoints"`.
    - `@dataclass(frozen=True) class Unfinished: folder: Path; moment: Build; last_at: datetime; done: int`.
    - `start(folder: Path, moment: Build, process: str) -> None`: writes
      `run-state.json` `{"moment": {...}, "finished": false, "spent": {...}}`,
      keeping earlier processes' `spent` entries and adding `process: 0.0`.
    - `write(folder: Path, comparison_id: str, fingerprint: str, data: dict, at: datetime) -> None`:
      `checkpoints/<slug>_<sha8>.json` holding `comparison`, `fingerprint`, `at`
      (ISO) and `slice`; replaced whole (temp file, `os.replace`).
    - `read_all(folder: Path) -> dict[str, tuple[str, dict]]`: comparison id to
      (fingerprint, slice); an unreadable file is skipped with a printed line.
    - `record_spend(folder: Path, process: str, usd: float) -> None`,
      `total_spend(folder: Path) -> float`, `finish(folder: Path) -> None`.
    - `find_unfinished(root: Path, view: str) -> Unfinished | None`: the folder
      under `root / view` whose state is not finished and which holds at least 1
      checkpoint, latest `last_at` first.
    - `clear(folder: Path) -> None`: removes `checkpoints/`, `run-state.json`
      and `triage-progress.json`; leaves `run.json`, `result.md`, `triage.json`.

- [ ] **Step 1: Write the failing tests** (`T/test_checkpoints.py`, all on
      `tmp_path`)

- `test_a_checkpoint_round_trips_and_replaces_its_earlier_copy`: write
  `"ada-region"` twice with fingerprints `"a"` then `"b"`; `read_all` returns
  `{"ada-region": ("b", {...second slice...})}`.
- `test_an_unfinished_folder_is_found_by_its_latest_checkpoint`: 2 folders, one
  finished, one with checkpoints at `T0` and `T0 + 1h`; returns the unfinished
  one with `last_at == T0 + 1h`, `done == 2`.
- `test_a_started_folder_without_a_checkpoint_is_not_unfinished`: `start` only;
  `find_unfinished` returns None.
- `test_spend_adds_up_across_processes`: `start(..., "p1")`,
  `record_spend(p1, 0.4)`, `start(..., "p2")`, `record_spend(p2, 0.3)`;
  `total_spend == pytest.approx(0.7)`.
- `test_clear_keeps_the_finished_results`: folder with `run.json`,
  `triage.json`, `triage-progress.json`, `run-state.json`, a checkpoint; after
  `clear` only `run.json` and `triage.json` remain.

- [ ] **Step 2: Run to fail** — no module `checkpoints`.

- [ ] **Step 3: Implement** as the Interfaces say.

- [ ] **Step 4: Run to pass; commit** —
      `feat(cube): keep run checkpoints in the run folder`, `Refs #6410`.

---

### Task 9: `run` checkpoints each comparison and resumes after a stop

**Files:**

- Modify: `P/pipeline.py:1316-1474` (`run`), `P/cli.py:254-259` (flags),
  `437-449` (dispatch)
- Test: `T/test_cli.py`

**Interfaces:**

- Consumes: Task 7's `_compare_one`, `_Sides.merge/to_json/from_json`,
  `side_fingerprints`, `checkpoint_fingerprint`; Task 8's `checkpoints`.
- Produces:
  - `AUTO_RESUME = timedelta(hours=24)`, `RESUME_LIMIT = timedelta(days=7)` in
    `pipeline.py`.
  - `run(cfg, *, wh, cube, now, requested, max_usd, cache_root, cube_host="", resume: bool = False, restart: bool = False, clock: Callable[[], datetime] = <UTC now>) -> RunResult`.
  - CLI: `run --resume` and `run --restart`, mutually exclusive; `--resume` with
    `--moment` refuses ("`--moment` picks the moment itself; drop `--resume`").
    `cli` passes `clock=utcnow`.

- [ ] **Step 1: Write the failing tests** (`T/test_cli.py`)

Helper `_four(tmp_path)`: `YML` with the `ada-region` comparison repeated as
`ada-region-1` to `ada-region-4` (same probe, so one `PROBE_FP`). `FakeBigQuery`
takes `fail_once: str | None`: the first script whose text holds that string
gets a job whose `result()` raises
`BadRequest("over", errors=[{"reason": "bytesBilledLimitExceeded"}])`, which
`rows` turns into `CostCapError`; then `fail_once` resets to None.

```python
def test_a_stopped_run_resumes_to_the_same_result(fakes, tmp_path, monkeypatch):
    path = _four(tmp_path)
    # Baseline: an uninterrupted run in its own cache.
    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "whole")
    assert cli.main(["run", str(path)]) == 0
    whole = json.loads(next((tmp_path / "whole").glob("v/*/run.json")).read_text())

    monkeypatch.setattr(cli, "cache_root", lambda: tmp_path / "cache")
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["run", str(path)]) == 1
    folder = next((tmp_path / "cache" / "v").iterdir())
    # Comparisons run in config order: 1 and 2 finished, 3 failed, 4 never began.
    assert sorted(checkpoints.read_all(folder)) == ["ada-region-1", "ada-region-2"]

    fakes.bq.ran.clear()
    assert cli.main(["run", str(path)]) == 0
    scripts = [s for s in fakes.bq.ran if "-- outer" in s]
    assert len(scripts) == 2
    assert "ada_region_3" in scripts[0] and "ada_region_4" in scripts[1]
    resumed = json.loads((folder / "run.json").read_text())
    assert {**resumed, "cost_usd": 0} == {**whole, "cost_usd": 0}


def test_a_run_stopped_a_day_ago_waits_for_resume_or_restart(fakes, tmp_path, monkeypatch, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["run", str(path)]) == 1
    monkeypatch.setattr(cli, "utcnow", Clock(NOW + timedelta(hours=30)))
    assert cli.main(["run", str(path)]) == 1
    assert "pass --resume to finish it at that moment, or --restart" in capsys.readouterr().err
    assert cli.main(["run", str(path), "--resume"]) == 0


def test_a_resume_past_time_travel_refuses_before_any_query(fakes, tmp_path, monkeypatch, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["run", str(path)]) == 1
    # The checkpoint is fresh, but the build began more than 7 days ago less the margin.
    monkeypatch.setattr(cli, "utcnow", Clock(START + timedelta(days=7)))
    folder = next((tmp_path / "cache" / "v").iterdir())
    for f in (folder / "checkpoints").glob("*.json"):  # age the checkpoints to 1 hour
        data = json.loads(f.read_text()); data["at"] = (START + timedelta(days=7, hours=-1)).isoformat()
        f.write_text(json.dumps(data))  # fmt: skip
    fakes.bq.ran.clear()
    assert cli.main(["run", str(path)]) == 1
    assert "pass --restart" in capsys.readouterr().err
    assert not [s for s in fakes.bq.ran if "-- outer" in s]


def test_restart_clears_the_unfinished_run(fakes, tmp_path):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["run", str(path)]) == 1
    fakes.bq.ran.clear()
    assert cli.main(["run", str(path), "--restart"]) == 0
    assert len([s for s in fakes.bq.ran if "-- outer" in s]) == 4


def test_a_comparison_edited_since_its_checkpoint_is_compared_again(fakes, tmp_path, capsys):
    path = _four(tmp_path)
    fakes.bq.fail_once = "ada_region_3"
    assert cli.main(["run", str(path)]) == 1
    # `workbook` is outside the probe's fingerprint, so `run` does not refuse it.
    path.write_text(path.read_text().replace("workbook: wb-1", "workbook: wb-9", 1))
    fakes.bq.ran.clear()
    assert cli.main(["run", str(path)]) == 0
    assert "Comparison ada-region-1: its config or SQL changed since its saved result" in capsys.readouterr().out
    # ada-region-1 again (edited), then 3 and 4 (never finished); 2 is kept.
    assert len([s for s in fakes.bq.ran if "-- outer" in s]) == 3
```

Also: `run.json`'s `cost_usd` after a resume equals `checkpoints.total_spend` of
the folder (both processes), and `--resume` with nothing unfinished refuses with
"no unfinished run of v to resume".

- [ ] **Step 2: Run to fail** — FAIL (no resume, sequential compare).

- [ ] **Step 3: Implement `run`.** The order the tests pin:

```text
1. Refuse --resume with requested; the checks before the budget stay as today.
2. Inside wh.budget(max_usd):
   a. requested: pick_moment as today; folder = report.run_dir(...); reuse its
      checkpoints only when its state is unfinished (no age rule).
   b. else unfinished = checkpoints.find_unfinished(cache_root, view):
      restart -> checkpoints.clear(unfinished.folder), then as (d).
      age < AUTO_RESUME, or resume and age <= RESUME_LIMIT -> reuse its moment.
        Print "Resuming the unfinished run of <start> to <end>: <done> of <n>
        comparisons saved, the last at <last_at>."
      AUTO_RESUME <= age <= RESUME_LIMIT -> Refusal "<view>: an unfinished run of
        <stamp> stopped <h> hours ago; pass --resume to finish it at that
        moment, or --restart to start a new run".
      age > RESUME_LIMIT -> Refusal "...stopped more than 7 days ago, past time
        travel; pass --restart to start a new run".
   c. A reused moment goes through pick_moment([build], now, None) first; its
      MomentError becomes a Refusal naming --restart.
   d. No reuse: fact_builds + pick_moment as today; if the folder has a state,
      checkpoints.clear it.
   e. checkpoints.start(folder, build, process=clock().isoformat()).
3. Saved slices: for each comparison with a checkpoint, compare
   checkpoint_fingerprint(c, side_fingerprints(...)) with the saved one; equal
   -> keep the slice; else print "Comparison <id>: its config or SQL changed
   since its saved result; comparing it again."
4. The rest, one at a time in config order, each given the merged `moved` so
   far. After each: write its checkpoint (at=clock()) and
   record_spend(folder, process, wh.spent). On an exception: record spend, then
   re-raise; the comparisons before it are already checkpointed.
5. Merge every slice into one _Sides in config order, saved and fresh alike.
6. The rest of run as today; cost_usd = total_spend after a last record_spend.
   After run.json is written: checkpoints.finish(folder).
```

- [ ] **Step 4: Run to pass** — `... pytest T/ -q`.

- [ ] **Step 5: Commit** —
      `feat(cube): run checkpoints each comparison and resumes after a stop`,
      `Refs #6410`.

---

### Task 10: Proofs read the saved table; the session path goes

**Files:**

- Modify: `P/confirm.py:622-738` (`unmatched_sql`, `frozen_sql` →
  `bucket_rows_sql`), `748-762` (`StudentCount`), `1019-1136` (`run_proof`,
  `_student_count`, `_freeze`), `1580-1660` (`run_stored`, `_run_one`),
  `1859-1881` (`run_confirm`), `check_proofs` (Task 3)
- Modify: `P/trace.py:973-1003` (`Prepared`), `P/bq.py` (delete `session`,
  `freeze`, `_session_settings`, `_SESSION_REF`, `_in_session`, `_session_id`,
  `_frozen`)
- Test: `T/test_confirm.py` (fake `Wh` lines 85-118; delete
  `test_a_frozen_bucket_proves_as_the_rebuilt_one_and_freezes_once` line 888 and
  `test_a_proof_that_fits_runs_inline_without_freezing` line 983),
  `T/test_bq.py` (delete lines 482-540)

**Interfaces:**

- Consumes: `saved.table_id/table_sql/labels`,
  `pipeline.checkpoint_fingerprint`, `pipeline.save_script`,
  `pipeline.inline_unmatched`, `Warehouse.saved_labels`.
- Produces:
  - `confirm.require_saved(wh: Warehouse, cfg: ViewConfig, run: RunResult, comparison: Comparison) -> str`:
    the table as SQL, or `pipeline.Refusal`:
    - missing:
      `f"comparison {id!r}: no saved rows for the run of {utc_literal(run.moment.end)}; they expired or were never saved."`
    - a label differs:
      `f"comparison {id!r}: the saved rows are labelled for another run or SQL ({', '.join(sorted(differing keys))})."`
    - Both end with the same next step, chosen by the moment's age: within time
      travel (`timetravel` margin included),
      ``Run `run --moment '<m>' --restart` to save them again``; past it,
      ``Start a new `run`: this moment is past BigQuery's 7 days of time travel``.
      Saved tables outlive time travel (14 days against 7), so the second is the
      usual case for a missing table. A test pins each wording.
  - `confirm.bucket_rows_sql(comparison: Comparison, bucket: str, source: str) -> str`:
    `frozen_sql`'s columns from `source` (`WHERE bucket = '<bucket>'`): the
    grain from `__gd<i>` for `dashboard_only`, else `__gc<i>`, under Cube names;
    `__cut<j>` from `__dk<j>` or `__ck<j>` the same way; `side` from the bucket.
  - `confirm.unmatched_sql(comparison: Comparison, bucket: str, items: list[tuple[str, Group]], source: str) -> tuple[str, str]`:
    ctes `WITH __f AS (<bucket_rows_sql>)` and the select over `__f`.
    `StudentCount.source` is always `__f`.
  - `confirm.proof_sql(wh, cfg, comparison, sides: pipeline.RowSides, proof: Proof, items, build: Build, *, table: str, moved: dict[str, bool] | None = None, students: bool = False) -> tuple[str, set[str]]`:
    check, pin (`trace._one_moment` as today) and build the counting query;
    returns it and its literals. Runs no priced query.
  - `run_proof(wh, cfg, comparison, sides, proof, items, build, moved=None, students=None, *, table: str) -> dict[str, Outcome]`:
    `proof_sql`, then estimate, cap check, `rows` and `outcomes` as today.
  - `check_proofs` reads
    `f"({pipeline.inline_unmatched(cfg, comparison, sides)})"` as its source.

- [ ] **Step 1: Write the failing tests** (`T/test_confirm.py`)

The fake `Wh` loses `session` and `freeze`, gains `labels: dict[str, dict]`,
`saved_labels(table_id)` (`self.labels.get(table_id)`) and `script`. A helper
`_save(duck, wh, run, cfg=CFG)` runs, for each comparison with rows,
`pipeline.save_script(cfg, c, SIDES, saved.table_sql(table_id), None)` through
`duck.rows`, and sets
`wh.labels[table_id] = saved.labels(cfg.view, BUILD, c.id, pipeline.checkpoint_fingerprint(c, run.fingerprints.get(c.id, {})))`.
`_stored` and `_reprove` call `_save` first, so every existing proof test runs
against a saved table.

```python
def test_a_proof_reads_the_saved_rows_not_both_sides(duck, tmp_path, offline):
    _tables(duck)
    wh = Wh(duck)
    (item,) = _reprove(duck, tmp_path, _run([_group(3)]), wh=wh)
    ((sql, _),) = wh.ran
    assert item["suggestion"] == "cause"
    assert "`cube_validation_scratch`" in sql and "cube_t" not in sql


def test_a_proof_refuses_when_its_saved_rows_are_gone(duck, tmp_path, offline, capsys):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    items = _items(run)
    directory, _ = _proof(tmp_path)
    confirm.apply_runs(run, items, confirm.run_stored(CFG, run, directory, wh=wh, cube=None), CFG)
    assert items[0]["suggestion"] == "investigate" and wh.ran == []
    assert "no saved rows for the run of" in capsys.readouterr().out


def test_a_proof_refuses_saved_rows_labelled_for_another_run(duck, tmp_path, offline, capsys):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    (table,) = wh.labels
    wh.labels[table] = {**wh.labels[table], "fingerprint": "0" * 32}
    items = _items(run)
    directory, _ = _proof(tmp_path)
    confirm.apply_runs(run, items, confirm.run_stored(CFG, run, directory, wh=wh, cube=None), CFG)
    assert wh.ran == []
    assert "labelled for another run or SQL (fingerprint)" in capsys.readouterr().out
```

- [ ] **Step 2: Run to fail** — FAIL (the proof still rebuilds both sides).

- [ ] **Step 3: Implement** as the Interfaces say; `_run_one` and `run_confirm`
      call `require_saved` before `run_proof` (its Refusal lands in `ran.why`,
      as today's refusals do). Delete the session path in `bq.py`, `confirm.py`
      and `trace.py`, and rewrite `Prepared`'s docstring without frozen tables.

- [ ] **Step 4: Verify nothing reads the old path**

Run:
`rg -n "_freeze|frozen_sql|\.freeze\(|wh\.session|_SESSION_REF|\.frozen\b" W/scripts W/tests`
Expected: no output.

Run: `... pytest T/ -q` — PASS.

- [ ] **Step 5: Commit** —
      `feat(cube): proofs read each comparison's saved rows; drop session temp tables`,
      `Refs #6410`.

---

### Task 11: Triage prices up front and keeps its progress

**Files:**

- Create: `P/progress.py`, `T/test_progress.py`
- Modify: `P/confirm.py:1580-1660` (`run_stored`), `P/triage.py:1152-1276`
  (`run_triage`), `P/cli.py:261-287`, `451-463`
- Test: `T/test_confirm.py`, `T/test_cli.py`

**Interfaces:**

- Consumes: `confirm.proof_sql`, `confirm.require_saved`, `trace._dry_runs`,
  `Warehouse.refuse_past_caps`, `triage._open_key`.
- Produces:
  - `progress.FILE = "triage-progress.json"`;
    `progress.key(proof_fingerprint: str, comparison_id: str, bucket: str, sql_fingerprints: dict[str, str], open_keys: Iterable[str]) -> str`
    (sha256 of the JSON of the 5, `open_keys` sorted);
    `progress.load(folder: Path) -> dict[str, dict]`;
    `progress.save(folder: Path, key: str, outcome: dict) -> None` (whole-file
    replace through a temp file and `os.replace`, so a stop mid-write keeps the
    last whole file).
  - An outcome is
    `{"found": {open_key: {"n_rows", "counts": {cause: n}, "unexplained"}}, "students": [...]}`;
    only a proof that ran to an outcome is saved.
  - `run_stored(cfg, run, directory, *, wh, cube, prepared=None, progress_dir: Path | None = None, comparisons: set[str] | None = None) -> list[Ran]`.
  - `run_triage(..., comparisons: list[str] | None = None)`; CLI
    `triage --comparison <id>` (repeatable, `action="append"`).

- [ ] **Step 1: Write the failing tests**

`T/test_progress.py`: `key` is stable for reordered `open_keys` and differs when
any of the 5 parts differs; `save` then `load` round-trips 2 keys.

`T/test_confirm.py` (pass `progress_dir=tmp_path`):

```python
def test_a_second_triage_reuses_a_finished_proof_and_runs_no_query(duck, tmp_path, offline):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _proof(tmp_path)
    first = confirm.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    again = confirm.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    assert len(wh.ran) == 1
    assert again[0].found == first[0].found and again[0].students == first[0].students


def test_an_edited_proof_or_a_new_group_runs_again(duck, tmp_path, offline):
    _tables(duck)
    run, wh = _run([_group(3)]), Wh(duck)
    _save(duck, wh, run)
    directory, _ = _proof(tmp_path)
    confirm.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    _proof(tmp_path, causes={"C1": CAUSES["C2"], "C2": CAUSES["C1"]})
    confirm.run_stored(CFG, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    bigger = _run([_group(4)])
    confirm.run_stored(CFG, bigger, directory, wh=wh, cube=None, progress_dir=tmp_path)
    assert len(wh.ran) == 3


def test_proofs_refuse_before_any_runs_when_their_estimate_passes_a_cap(duck, tmp_path, offline):
    class Capped(Wh):
        def refuse_past_caps(self, usd):
            if usd > 0.015:
                raise CostCapError(f"these queries (${usd:.2f}) would pass the $0.01 cap")

    _tables(duck)
    run, wh = _sibling_run(), Capped(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _proof(tmp_path)
    with pytest.raises(CostCapError, match=r"\(\$0\.02\)"):
        confirm.run_stored(CFG2, run, directory, wh=wh, cube=None)
    assert wh.ran == []


def test_a_triage_stopped_partway_keeps_the_proofs_it_finished(duck, tmp_path, offline):
    class StopsOnSecond(Wh):
        def rows(self, sql, timeout_s=None):
            if len(self.ran) == 1:
                raise CostCapError("nothing is left under --max-usd")
            return super().rows(sql, timeout_s)

    _tables(duck)
    run, wh = _sibling_run(), StopsOnSecond(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _proof(tmp_path)
    first = confirm.run_stored(CFG2, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    assert [r.found is not None for r in first] == [True, False]
    assert len(progress.load(tmp_path)) == 1

    wh = Wh(duck)
    _save(duck, wh, run, cfg=CFG2)
    confirm.run_stored(CFG2, run, directory, wh=wh, cube=None, progress_dir=tmp_path)
    assert len(wh.ran) == 1  # only the proof the first triage did not finish


def test_triage_of_one_comparison_reuses_the_others_and_runs_only_its_own(duck, tmp_path, offline):
    _tables(duck)
    run, wh = _sibling_run(), Wh(duck)
    _save(duck, wh, run, cfg=CFG2)
    directory, _ = _proof(tmp_path)
    kept, empty = tmp_path / "kept", tmp_path / "empty"
    confirm.run_stored(CFG2, run, directory, wh=wh, cube=None, progress_dir=kept)
    wh.ran.clear()

    reused = confirm.run_stored(CFG2, run, directory, wh=wh, cube=None,
                                progress_dir=kept, comparisons={"mastery-b"})  # fmt: skip
    assert wh.ran == [] and all(r.found is not None for r in reused)

    alone = confirm.run_stored(CFG2, run, directory, wh=wh, cube=None,
                               progress_dir=empty, comparisons={"mastery-b"})  # fmt: skip
    assert len(wh.ran) == 1
    by = {confirm._comparison_of(r): r for r in alone}
    assert by["mastery"].why == "proof mastery__cube_only.sql not run: outside --comparison"
    assert by["mastery-b"].found is not None
```

(`CostCapError` and `progress` are new imports; `_sibling_run`, `SIBLING` and
`CFG2` are at lines 1045-1073.)

`T/test_cli.py`: `triage <file> --comparison ada-region --no-trace` runs, writes
`triage.json` with every open item, and prints only `ada-region` items.

- [ ] **Step 2: Run to fail.**

- [ ] **Step 3: Implement `run_stored`:**

```text
1. Pairs (proof, comparison) as today (own + _shared), each with its bucket
   items; drop pairs with no items.
2. Per pair, its progress key; a saved outcome rebuilds Ran.found (open key ->
   the pair's item id) and Ran.students, and runs nothing.
3. A pair outside `comparisons` with no saved outcome:
   Ran.why = "proof <file> not run: outside --comparison".
4. The rest, in the main thread: require_saved, then proof_sql (refusals and
   errors into Ran.why, as _run_one catches today).
5. trace._dry_runs on every prepared query; a failed dry run goes into its
   Ran.why (bigquery_said). Print "Proofs: <n> to run, $<sum> (dry run);
   <k> reused from triage-progress.json." Then wh.refuse_past_caps(sum),
   whose CostCapError ends the triage before any proof runs.
6. One at a time, in pair order: wh.rows(sql, timeout_s=TIMEOUT_S), then
   outcomes (its Refusal or a CostCapError into Ran.why, as today), and
   progress.save() for a successful one before the next proof starts.
7. Return the Rans in pair order.
```

`run_triage` passes `progress_dir=run_json.parent` and `comparisons`; with
`comparisons`, the trace's `skip` adds every open group outside them, and
`batch_lines` prints only their items; `triage.json` holds every item.

- [ ] **Step 4: Run to pass** — `... pytest T/ -q`.

- [ ] **Step 5: Commit** —
      `feat(cube): triage prices its proofs first and keeps finished ones`,
      `Refs #6410`.

---

### Task 12: Skill and docs

**Files:**

- Modify: `W/.claude/skills/cube-validation/SKILL.md` (Read it first)
- Check: `W/docs/` pages in the `mkdocs.yml` nav, `W/scripts/CLAUDE.md`

- [ ] **Step 1: Edit the skill.** Read `.claude/rules/claude-md-editing.md` (it
      loads on the Read). Changes:
  - Step 7 (`run`): a stopped `run` resumes on its own within 24 hours of its
    last checkpoint, needs `--resume` or `--restart` from 24 hours to 7 days,
    and cannot resume past 7 days; `--moment` picks the moment itself;
    `cost_usd` adds every process's spend; unmatched rows go to
    `cube_validation_scratch` tables (14-day expiry, Data Team only) and never
    to the cache.
  - Step 8 (`triage`): proofs read those tables; a missing or mislabelled one
    refuses and names the next step (`run --moment ... --restart` within time
    travel, a new `run` past it); every proof is priced before any runs and a
    total over a cap refuses up front; finished outcomes kept in
    `triage-progress.json`, so a stopped triage skips them; `--comparison`
    (repeatable).
  - Step 7.7 (`triage confirm`): replace the 900K freeze paragraph (lines
    352-357) with "a proof reads its comparison's saved rows"; the guard list
    (line 343) says `student_number`, `employee_number` and other numbers that
    name a person, not every `_number`.
  - `--cells` (line 379): a `rows.cell: count_students` comparison is sized from
    per-cell distinct students; cut captions that vary are row columns.
  - Step 6 (`prove --check`): it also dry-runs every stored proof.
- [ ] **Step 2: Docs.**
      `rg -n -i "cube.validat|triage|session temp" W/docs --glob '!superpowers/**'`
      found no published page on the validator when this plan was written; rerun
      it and edit any page it lists. `scripts/CLAUDE.md`'s catalog line needs no
      change.
- [ ] **Step 3: Lint** — from inside `W`:
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-validation/SKILL.md </dev/null`;
      fix findings.
- [ ] **Step 4: Commit** —
      `docs(cube): the validator's saved rows, resume and up-front proof pricing`,
      `Refs #6410`.

---

### Task 13: Live check on the DDI view (owner approves each spend)

Runs through the `cube-validation` skill's runner
(`/workspaces/teamster/tests/test_zz_cube_validation.py`, `PKG` =
`W/scripts/cube_validation`, deleted after each step), with `--project W`. Needs
Task 4's dataset. Read the DDI view file from the
`cristinabaldor/test/claude-ddi-cube-validation` branch's worktree. Before each
step, tell the owner the command and its `--max-usd`, and wait for a yes. Time
each step in the runner with `time.monotonic()`.

- [ ] **Step 1: Dataset** —
      `mcp__claude_ai_Google_Cloud_BigQuery__get_dataset_info` on
      `cube_validation_scratch`: location `US`, default expiration 14 days, the
      access list the owner set.
- [ ] **Step 2: `prove --check`** — every stored DDI proof dry-runs; list the
      rejected ones.
- [ ] **Step 3: One `run`, stopped and resumed** — `run` in the background
      runner; stop it after about 10 minutes (stop the pytest process by its
      PID, not `pgrep -f` on a string in your own command); then `run` again.
      Expected: "Resuming ..." and only the unfinished comparisons compared;
      `cost_usd` adds both processes. Report the total time; `run` has no time
      target. One run, not a baseline plus a resumed one: Task 9's offline test
      pins that a resumed `run.json` equals an uninterrupted one. Spot-check one
      saved table with `get_table_info`: its 4 labels, its expiry, its `bucket`
      column.
- [ ] **Step 4: Removed** (folded into Step 3).
- [ ] **Step 5: Triage** — `triage --no-trace`. Benchmark, not a pass/fail:
      report its time against 10 minutes, and the trace's time separately. A
      slower result is reported, never fixed by dropping a check. Then stop a
      second `triage --no-trace` partway and run it again: the proofs it
      finished are reused ("reused from triage-progress.json") and
      `triage.json`'s items equal the first one's.
- [ ] **Step 6: Caps** —
      `run --moment <M, Step 3's moment> --restart --max-usd 0.01` refuses
      before saving any table (check `maximum_bytes_billed` holds for a
      multi-statement job); `triage --max-usd 0.01` refuses up front naming the
      proofs' total.
- [ ] **Step 7: #6411 and #6412 on DDI** — `triage confirm --cells` on one
      `students-bucket-*` and one `mastery-bucket-*` comparison (after setting
      `rows.cell: count_students` on the students ones in the DDI branch, a
      validation-file commit there); report the cells left open, if any (the
      issue's "few cells outside proven groups" is unverified).
- [ ] **Step 8: Report** the 2 times, the resume result, and any gap, on #6410
      as a comment the owner approves first.

---

## Settled at plan review (2026-11-13)

- A missing or mislabelled saved table: triage refuses with the next step by the
  moment's age (Task 10). Within time travel that is
  `run --moment <m> --restart`, which recompares every comparison; a
  `run --comparison` to redo one is not built, since a table goes missing within
  7 days only when someone drops it.
- A plain `run` on a moment whose run finished starts fresh (clears that
  folder's checkpoints), as `run` does today.
- `triage --comparison` writes a whole `triage.json`: other comparisons take
  their saved outcomes, or are noted "not run: outside --comparison".
- `rows.cell` takes `count_students` only; the DDI comparisons are counts, so a
  share of distinct students waits for a view that has one. It costs `run` one
  more query per `count_students` comparison.
- Time is a benchmark, not a rule: a `--no-trace` triage is measured against 10
  minutes, and no check, guard or refusal is cut or loosened to reach it (spec,
  _Revision 2026-11-13_).
- No parallel workers in `run` or `triage` (spec, _Revision 2026-11-13_): the
  owner validates one cube or measure at a time, and saved tables carry the
  triage speedup.
- Whether `maximum_bytes_billed` bounds a multi-statement job as a whole or per
  statement is unverified; Task 13 Step 6 checks it.
