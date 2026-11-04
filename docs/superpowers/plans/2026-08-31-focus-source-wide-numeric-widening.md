# Focus source-wide numeric widening implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every unbounded Postgres `numeric` in the KIPP Miami Focus source
loads as BigQuery BIGNUMERIC, so no future value can crash the sync, and the
per-table `widen_unbounded_numeric` opt-in is deleted.

**Architecture:** 2 pull requests then 1 manual run. PR 1 adds 94
`cast(<col> as numeric)` projections to 40 `stg_focus__*` models, which are
no-ops against today's NUMERIC columns. PR 2 applies the widening adapter to
every table and deletes the routing machinery. A manual Focus run with
`refresh: drop_resources` then drops and recreates the tables so BigQuery
accepts the new types.

**Tech Stack:** dbt 1.11 on BigQuery, Dagster with `dagster-dlt`, dlt 1.29,
SQLAlchemy reflection, `uv` for Python, `trunk` for linting.

## Global Constraints

- Spec:
  `docs/superpowers/specs/2026-08-31-focus-source-wide-numeric-widening-design.md`.
  Issue [#5080](https://github.com/TEAMSchools/teamster/issues/5080).
- Always `uv run`. Never bare `python`, `dbt`, or `dagster`.
- PR 1 branch: `cbini/feat/claude-focus-source-wide-numeric`, worktree
  `/workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric`. Use
  `git -C <worktree>` on every git call.
- PR 2 needs a NEW branch off `origin/main`, created only after PR 1 merges. Ask
  the user for issue and worktree choices before creating it, per `CLAUDE.md`.
  Tasks 3 to 6 write `<PR 2 branch>` and `<PR 2 worktree>`. Both are unknown
  until that step, and Task 3 Step 0 fixes their values. Substitute the real
  values everywhere before running any command that contains them.
- Casts go after the last bare column reference and before any expression block,
  because sqlfluff ST06 sorts simple targets ahead of complex ones. A `cast()`
  is a simple target.
- Never run `trunk fmt`. The pre-commit hook formats. Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <paths> </dev/null`
  from inside the worktree before pushing.
- Contracts are enforced on `focus.staging` by `src/dbt/focus/dbt_project.yml`.
  A missed cast fails `dbt build`, so the build is the test.
- Do not touch Illuminate's `unbounded_numeric_adapter`.

## File Structure

| File                                                                | Responsibility                                                                   | PR  |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------- | --- |
| 40 `src/dbt/focus/models/staging/stg_focus__*.sql`                  | project 94 columns through `cast(... as numeric)` so contracts stay on `numeric` | 1   |
| `src/teamster/libraries/dlt/focus/assets.py`                        | apply `_widening_type_adapter` to every table; drop the routing parameters       | 2   |
| `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`         | drop the `widen_numeric_tables` frozenset                                        | 2   |
| `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml` | drop both `widen_unbounded_numeric` keys                                         | 2   |
| `tests/libraries/test_dlt_focus_type_adapter.py`                    | assert every table gets the widening adapter                                     | 2   |
| `src/teamster/libraries/dlt/CLAUDE.md`                              | correct the stale Focus table count                                              | 2   |

No `.yml` properties files change. Every affected column already declares
`data_type: numeric`, and a cast preserves both the name and the declared type.

---

### Task 1: Add the 94 casts to 40 staging models

**Files:**

- Modify: 40 files under `src/dbt/focus/models/staging/`, listed in the
  `CAST_MAP` below
- Test: `uv run dbt build --select package:focus` (contracts are the test)

**Interfaces:**

- Consumes: nothing from earlier tasks
- Produces: staging models whose `points`-style columns survive a BIGNUMERIC
  source. Task 4 depends on these being merged first.

- [ ] **Step 1: Confirm the baseline is green before changing anything**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric \
  && VIRTUAL_ENV= uv run --active dbt deps \
    --project-dir "$PWD/src/dbt/kippmiami" \
  && VIRTUAL_ENV= uv run --active dbt build --select package:focus \
    --project-dir "$PWD/src/dbt/kippmiami"
```

Expected: `ERROR=0`. Relationship-test warnings are pre-existing; ignore them.
If anything ERRORs here, stop and report — it is not caused by this plan.

- [ ] **Step 2: Write the cast script**

Create `.claude/scratch/add-focus-casts.py`:

```python
import pathlib
import re

STAGING = pathlib.Path(
    "/workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric"
    "/src/dbt/focus/models/staging"
)

# model stem -> list of (source column, alias or None)
CAST_MAP: dict[str, list[tuple[str, str | None]]] = {
    "address": [("latitude", None), ("longitude", None)],
    "attendance_calendar": [("minutes", None)],
    "attendance_codes": [("sort_order", None), ("table_name", None)],
    "attendance_day": [
        ("minutes_absent", None),
        ("minutes_present", None),
        ("state_value", None),
    ],
    "attendance_period": [
        ("break_minutes", None),
        ("break_out_time", None),
        ("minutes_absent", None),
        ("minutes_present", None),
    ],
    "co_teacher_days": [
        ("f", None), ("h", None), ("m", None), ("s", None),
        ("t", None), ("u", None), ("w", None),
    ],
    "course_periods": [
        ("availability", None),
        ("filled_seats", None),
        ("sped_seats", None),
        ("total_seats", None),
    ],
    "course_weights": [
        ("credits", None), ("gpa_multiplier", None), ("year_fraction", None),
    ],
    "courses": [("course_hours", None), ("credit_hours", None), ("length", None)],
    "custom_field_select_options": [("sort_order", None)],
    "discipline_referrals": [("suspension_length", None)],
    "grad_subject_credits": [("credits", None)],
    "grad_subject_programs": [("sort_order", None)],
    "grad_subjects": [("credits", None), ("sort_order", None)],
    "gradebook_assignment_types_join_course_periods": [
        ("drop_lowest_grades", None), ("final_grade_percent", None),
    ],
    "gradebook_assignments": [("last_updated_user", None), ("points", None)],
    "gradebook_templates": [("drop_lowest_grade", None)],
    "marking_periods": [("sort_order", None), ("year_fraction", None)],
    "master_courses": [
        ("allow_repeat", None), ("course_hours", None), ("credit_hours", None),
        ("credits", None), ("total_credit", None),
    ],
    "referral_codes": [("priority", None)],
    "report_card_grades": [
        ("default_breakoff", None), ("gpa_averaging_cutoff", None),
        ("gpa_averaging_points", None), ("gpa_value", None),
        ("sort_order", None), ("weighted_gpa_value", None),
    ],
    "resources": [("seats", None)],
    "scheduling_teams": [("sort_order", None)],
    "school_gradelevels": [("sort_order", None)],
    "school_periods": [("length", None), ("sort_order", None)],
    "schools": [
        ("act_organization_code", None), ("latitude", None),
        ("longitude", None), ("sort_order", None),
    ],
    "standard_categories_1": [("sort_order", None)],
    "standard_categories_2": [("sort_order", None)],
    "standard_categories_3": [("sort_order", None)],
    "standard_categories_4": [("sort_order", None)],
    "standards": [("sort_order", None)],
    "student_enrollment": [("distance_from_school", None)],
    "student_enrollment_codes": [("sort_order", None)],
    "student_report_card_grades": [
        ("credits", None), ("credits_earned", None), ("gpa_points", None),
        ("percent_grade", None), ("weighted_gpa_points", None),
    ],
    "students": [
        ("custom_l1482", "powerschool_id"), ("custom_l1483", "disis_id"),
    ],
    "students_join_people": [("sort_order", None)],
    "test_history_parts": [("sort_order", None)],
    "test_history_score_types": [
        ("max_score", None), ("max_score1", None), ("max_score2", None),
        ("max_score3", None), ("max_score4", None), ("min_score", None),
        ("min_score1", None), ("min_score2", None), ("min_score3", None),
        ("min_score4", None), ("sort_order", None),
    ],
    "test_history_scores": [("score", None)],
    "users": [
        ("custom_200000002", "experience_length_years"),
        ("custom_l801", "w4_allowances_under_17"),
        ("custom_l802", "f_3_claim_dependent_and_other"),
    ],
}

BARE_REF = re.compile(r"^\s{4}\w+,$")


def projection_line(col: str, alias: str | None) -> re.Pattern[str]:
    """The existing line that projects `col`, aliased or not."""
    if alias is None:
        return re.compile(rf"^\s{{4}}{re.escape(col)},$")
    return re.compile(rf"^\s{{4}}{re.escape(col)} as {re.escape(alias)},$")


def rewrite(stem: str, cols: list[tuple[str, str | None]]) -> int:
    path = STAGING / f"stg_focus__{stem}.sql"
    lines = path.read_text().splitlines()

    # Remove each plain projection, asserting it appears exactly once.
    for col, alias in cols:
        pattern = projection_line(col, alias)
        hits = [i for i, line in enumerate(lines) if pattern.match(line)]
        if len(hits) != 1:
            raise SystemExit(
                f"{path.name}: {col} matched {len(hits)} projection lines, want 1"
            )
        del lines[hits[0]]

    # Insert after the LAST bare column reference, which puts the casts ahead
    # of any expression block and satisfies sqlfluff ST06.
    bare = [i for i, line in enumerate(lines) if BARE_REF.match(line)]
    if not bare:
        raise SystemExit(f"{path.name}: found no bare column reference to anchor to")
    at = bare[-1] + 1

    block = [""] + [
        f"    cast({col} as numeric) as {alias or col}," for col, alias in cols
    ]
    lines[at:at] = block

    path.write_text("\n".join(lines) + "\n")
    return len(cols)


def main() -> None:
    total = sum(rewrite(stem, cols) for stem, cols in sorted(CAST_MAP.items()))
    print(f"rewrote {len(CAST_MAP)} models, {total} casts")
    if total != 94 or len(CAST_MAP) != 40:
        raise SystemExit(f"expected 94 casts across 40 models, got {total}/{len(CAST_MAP)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the script**

Run:

```bash
cd /workspaces/teamster \
  && VIRTUAL_ENV= uv run --active python .claude/scratch/add-focus-casts.py
```

Expected: `rewrote 40 models, 94 casts` and exit 0. Any
`matched 0 projection lines` means a model changed shape — stop and re-derive
that entry rather than loosening the regex.

- [ ] **Step 4: Read 3 diffs by eye before trusting the other 37**

Run:

```bash
git -C /workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric \
  diff -- src/dbt/focus/models/staging/stg_focus__users.sql \
          src/dbt/focus/models/staging/stg_focus__students_join_people.sql \
          src/dbt/focus/models/staging/stg_focus__co_teacher_days.sql
```

Check 3 things. `stg_focus__users.sql` keeps its aliases, so it must read
`cast(custom_l801 as numeric) as w4_allowances_under_17,`.
`stg_focus__students_join_people.sql` must place the cast block BEFORE the
`custody = 'Y' as is_custodial,` block, not after it.
`stg_focus__co_teacher_days.sql` must show all 7 single-letter columns.

- [ ] **Step 5: Build, which is the contract test**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric \
  && VIRTUAL_ENV= uv run --active dbt build --select package:focus \
    --project-dir "$PWD/src/dbt/kippmiami"
```

Expected: `ERROR=0`, with the same warning count as Step 1. A contract error
naming a column and `numeric` means that model's cast is missing or misspelled.

- [ ] **Step 6: Lint**

Run from inside the worktree, and background it because 40 files takes over 2
minutes:

```bash
cd /workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
    src/dbt/focus/models/staging/ </dev/null
```

Expected: no `ST06` and no `LT02`. `Incorrect formatting ... prettier` alone is
fine, because the pre-commit hook fixes it. If ST06 fires, the cast block landed
after an expression block — move it above.

- [ ] **Step 7: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini-feat-focus-source-wide-numeric
git -C "$wt" add -u
git -C "$wt" commit -m "fix(dbt): cast Focus unbounded numeric columns back to numeric

Widening every unbounded Postgres numeric source-wide retypes 191 columns to
BigQuery BIGNUMERIC. These 94 columns are the ones a staging model projects,
so each casts back to numeric to hold its contract.

No-op today, because the columns are still NUMERIC. Merging this before the
Dagster change is what keeps the contracts valid across the cutover.

Refs #5080"
git -C "$wt" push
```

---

### Task 2: Open PR 1

**Files:**

- Create: `.claude/scratch/pr1-body.md`

**Interfaces:**

- Consumes: the branch pushed by Task 1
- Produces: a merged `main` carrying the 94 casts, which Task 3 requires

- [ ] **Step 1: Write the PR body**

Use `.github/pull_request_template.md` verbatim as the skeleton. Fill "Summary &
Motivation" with: this adds 94 casts across 40 Focus staging models; they are
no-ops today because the columns are NUMERIC; they exist so the contracts still
hold once #5080's Dagster change retypes those columns to BIGNUMERIC. Reference
`Refs #5080`, not `Closes`, because PR 2 finishes the issue.

Under "Reviewer Notes", say that the edits are script-generated from the dlt
reflected schema and that `dbt build --select package:focus` with contracts
enforced is the proof.

- [ ] **Step 2: Create the PR**

```bash
cd /workspaces/teamster \
  && gh api -X POST repos/TEAMSchools/teamster/pulls \
    -f title='fix: cast Focus unbounded numeric columns back to numeric' \
    -f head=cbini/feat/claude-focus-source-wide-numeric \
    -f base=main \
    -F body=@.claude/scratch/pr1-body.md \
    --jq '.number, .html_url'
```

- [ ] **Step 3: Wait for CI, then hand off**

Poll with `gh pr checks <number> --json name,bucket`. dbt Cloud is the check
that matters. Report the result and stop. Merging needs an analytics-engineers
approval and is the user's call.

---

### Task 3: Make the widening test fail

Do this task only after PR 1 merges.

- [ ] **Step 0: Create the PR 2 branch**

Ask the user 2 questions before touching git: whether to anchor PR 2 with its
own issue, and worktree or branch switch. Then follow the matching path in
`CLAUDE.md` under _Branches and worktrees_, basing the branch on `origin/main`
rather than local `main`. Suggested name:
`cbini/refactor/claude-focus-widen-all-tables`. Record the resulting branch and
worktree paths and substitute them for `<PR 2 branch>` and `<PR 2 worktree>`
through the rest of this plan.

**Files:**

- Modify: `tests/libraries/test_dlt_focus_type_adapter.py:283-305`

**Interfaces:**

- Consumes: `_build_focus_resource`, `_widening_type_adapter` from
  `teamster.libraries.dlt.focus.assets`
- Produces: a red test that Task 4 turns green

- [ ] **Step 1: Replace the opt-in test with a source-wide one**

Delete `test_widen_numeric_flag_selects_the_type_adapter` entirely and put this
in its place:

```python
def test_every_table_gets_the_widening_adapter(monkeypatch):
    """No table opts in any more — widening is source-wide."""
    from teamster.libraries.dlt.focus import assets as focus_assets

    captured: dict[str, Any] = {}

    def spy_table_rows(**kwargs):
        captured[kwargs["table"]] = kwargs["type_adapter_callback"]
        return iter(())

    monkeypatch.setattr(focus_assets, "table_rows", spy_table_rows)

    for table_name in ("plain", "was_opted_in"):
        resource = focus_assets._build_focus_resource(
            sql_database_credentials=ConnectionStringCredentials("sqlite://"),
            table_name=table_name,
            db_schema="public",
        )
        list(resource())

    assert captured["plain"] is focus_assets._widening_type_adapter
    assert captured["was_opted_in"] is focus_assets._widening_type_adapter
```

- [ ] **Step 2: Run it and confirm it fails**

Run:

```bash
cd <PR 2 worktree> \
  && VIRTUAL_ENV= uv run --active pytest \
    tests/libraries/test_dlt_focus_type_adapter.py::test_every_table_gets_the_widening_adapter -v
```

Expected: FAIL. `captured["plain"]` is `interval_to_microseconds_adapter`, not
`_widening_type_adapter`, because `_build_focus_resource` still defaults
`widen_numeric=False`.

---

### Task 4: Delete the opt-in plumbing

**Files:**

- Modify: `src/teamster/libraries/dlt/focus/assets.py`
- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/assets.py:33-41`
- Test: `tests/libraries/test_dlt_focus_type_adapter.py`

**Interfaces:**

- Consumes: the red test from Task 3
- Produces:
  `build_focus_dlt_assets(sql_database_credentials, code_location, tables, op_tags=None)`
  and
  `build_focus_source(sql_database_credentials, tables, signatures=None, db_schema=FOCUS_DB_SCHEMA)`
  — both without `widen_numeric_tables`. Task 5 edits the caller config that
  these signatures no longer accept.

- [ ] **Step 1: Drop the parameter from `_focus_table_items`**

Remove the `type_adapter` parameter and its default. Inside the call to
`table_rows`, pass `type_adapter_callback=_widening_type_adapter` directly.

- [ ] **Step 2: Drop `widen_numeric` from `_build_focus_resource`**

Remove the `widen_numeric: bool = False` parameter and the conditional. The call
to `_focus_table_items` loses its `type_adapter=` argument entirely.

- [ ] **Step 3: Drop `widen_numeric_tables` from both factories**

Remove the parameter from `build_focus_source` and `build_focus_dlt_assets`, and
remove it from the 3 places they pass it onward: the `_build_focus_resource`
call inside `build_focus_source`, the `dlt_source=build_focus_source(...)` call
in the `@dlt_assets` decorator, and the `build_focus_source(...)` call inside
`_assets`.

- [ ] **Step 4: Fix the 2 docstrings that now lie**

`_widening_type_adapter`'s docstring says "for tables that opt into numeric
widening". Replace with:

```python
    """Both Focus type adapters, applied to every table in the source."""
```

In `widen_unbounded_numeric_adapter`, the paragraph beginning "That retype is
also why this is opt-in per table" is now wrong. Replace that sentence with a
note that the retype is why the migration in #5080 reloaded every table once.
Add to the `Float` branch's paragraph that the guard now covers all 79 tables.

- [ ] **Step 5: Delete the caller's frozenset**

In `src/teamster/code_locations/kippmiami/dlt/focus/assets.py`, delete the
`widen_numeric_tables = frozenset(...)` assignment and the docstring below it,
and drop `widen_numeric_tables=widen_numeric_tables` from the
`build_focus_dlt_assets` call.

- [ ] **Step 6: Run the whole test file**

Run:

```bash
cd <PR 2 worktree> \
  && VIRTUAL_ENV= uv run --active pytest \
    tests/libraries/test_dlt_focus_type_adapter.py -v
```

Expected: all pass, including `test_every_table_gets_the_widening_adapter` and
the pre-existing `test_extract_invokes_both_adapters`.

- [ ] **Step 7: Commit**

```bash
wt=<PR 2 worktree>
git -C "$wt" add -u
git -C "$wt" commit -m "feat(dagster): widen every unbounded Focus numeric

The widening adapter now applies to every table, so a new unbounded numeric
column can no longer crash the sync on its first value past 9 decimal places.

Deletes the routing that existed only to avoid the one-time BIGNUMERIC retype:
the widen_numeric parameter, the widen_numeric_tables set, and the branch
between two adapters.

Refs #5080"
```

---

### Task 5: Delete the config keys and fix the stale docs

**Files:**

- Modify: `src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml`
- Modify: `src/teamster/libraries/dlt/CLAUDE.md`

**Interfaces:**

- Consumes: the factories from Task 4, which no longer read the YAML key
- Produces: a config with no dead keys

- [ ] **Step 1: Delete both `widen_unbounded_numeric` keys**

Two entries carry it: `student_gpa_calculated` and `gradebook_grades`. Delete
the key and the explanatory comment lines above it from both. Nothing reads the
key after Task 4, so leaving it would be dead config.

- [ ] **Step 2: Correct the stale table count**

`src/teamster/libraries/dlt/CLAUDE.md` says the sensor probes "all 76 tables"
and refers to "the other 75 tables". `focus.yaml` holds 79 entries, exactly 1 of
which is count-only. Change 76 to 79 and 75 to 78.

- [ ] **Step 3: Verify the config still parses into the right shape**

Run:

```bash
cd <PR 2 worktree> && VIRTUAL_ENV= uv run --active python -c "
import pathlib, yaml
a = yaml.safe_load(pathlib.Path(
  'src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml'
).read_text())['assets']
assert len(a) == 79, len(a)
assert not [x for x in a if 'widen_unbounded_numeric' in x], 'key survived'
assert all(x['cursor_column'] is not None for x in a if x['table_name'] != 'co_teachers')
print('ok', len(a), 'tables, no widen keys')
"
```

Expected: `ok 79 tables, no widen keys`.

- [ ] **Step 4: Confirm the module still imports**

`kippmiami.definitions` cannot load in a Codespace, because it resolves the
Focus database credential at import and that credential is unset. Compile the
edited files and import the library instead:

```bash
cd <PR 2 worktree> \
  && VIRTUAL_ENV= uv run --active python -m py_compile \
    src/teamster/libraries/dlt/focus/assets.py \
    src/teamster/code_locations/kippmiami/dlt/focus/assets.py \
  && VIRTUAL_ENV= uv run --active python -c \
    "import teamster.libraries.dlt.focus.assets as a; print(a._widening_type_adapter)"
```

Expected: both succeed and the function prints.

- [ ] **Step 5: Lint and commit**

```bash
cd <PR 2 worktree> \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
    src/teamster/libraries/dlt/focus/assets.py \
    src/teamster/code_locations/kippmiami/dlt/focus/assets.py \
    src/teamster/code_locations/kippmiami/dlt/focus/config/focus.yaml \
    src/teamster/libraries/dlt/CLAUDE.md \
    tests/libraries/test_dlt_focus_type_adapter.py </dev/null
```

Then:

```bash
wt=<PR 2 worktree>
git -C "$wt" add -u
git -C "$wt" commit -m "chore(dagster): drop the Focus widen_unbounded_numeric config key

Nothing reads the key now that widening is source-wide, so both entries that
set it become dead config.

Also corrects the Focus table count in libraries/dlt/CLAUDE.md, which said 76
while focus.yaml holds 79.

Refs #5080"
git -C "$wt" push
```

---

### Task 6: Open PR 2

**Files:**

- Create: `.claude/scratch/pr2-body.md`

**Interfaces:**

- Consumes: the branch pushed by Task 5
- Produces: the deploy that Task 7's cutover run depends on

- [ ] **Step 1: Write the PR body**

Use `.github/pull_request_template.md`. Summary: widening now applies to every
Focus table, and the opt-in machinery is deleted. Say `Closes #5080`.

Reviewer Notes must carry the cutover warning in plain sight: **merging this
breaks the Focus sync until someone runs the reload in Task 7.** Give the run
config inline so the reviewer sees the remedy next to the risk.

- [ ] **Step 2: Create the PR**

```bash
cd /workspaces/teamster \
  && gh api -X POST repos/TEAMSchools/teamster/pulls \
    -f title='feat: widen every unbounded Focus numeric and delete the opt-in' \
    -f head=<PR 2 branch> -f base=main \
    -F body=@.claude/scratch/pr2-body.md --jq '.number, .html_url'
```

- [ ] **Step 3: Report CI and stop**

Do not merge. Tell the user that merging starts the cutover clock and that Task
7 must follow within minutes.

---

### Task 7: The cutover run

This task is the user's to execute. A `refresh: drop_resources` run is a
destructive shared-resource mutation and the safety classifier blocks an agent
from launching it. Give the user these steps and verify the result afterwards.

**Files:** none.

**Interfaces:**

- Consumes: the deployed `kippmiami` code location carrying PR 2
- Produces: 44 retyped tables and a working sync

- [ ] **Step 1: Record the before state**

```sql
select count(*) as numeric_cols
from `teamster-332318.dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS`
where data_type = 'NUMERIC'
```

Note the number. It should be roughly 189, since `gradebook_grades` was already
retyped on 2026-08-31.

- [ ] **Step 2: Confirm the deploy landed**

Check that `get_location_load_history` for `kippmiami` shows the PR 2 merge
commit LOADED. Loading an older image would make the reload write the old types
back.

- [ ] **Step 3: The user launches the reload**

In the Dagster UI, materialize **all** `kippmiami/dlt/focus/*` assets with this
run config:

```yaml
ops:
  kippmiami__dlt__focus:
    config:
      refresh: drop_resources
```

All 79 rather than only the 44, because the 44-table list came from a schema
snapshot and a column added since would be missed. The 45 measured tables hold
799,554 rows and 173 MB, so this runs in minutes.

- [ ] **Step 4: Verify the after state**

```sql
select
  countif(data_type = 'NUMERIC') as numeric_cols,
  countif(data_type = 'BIGNUMERIC') as bignumeric_cols
from `teamster-332318.dagster_kippmiami_dlt_focus.INFORMATION_SCHEMA.COLUMNS`
```

Expected: `numeric_cols` drops to roughly 9, the columns with declared precision
in Postgres, and `bignumeric_cols` rises to roughly 207, which is 191 plus the
16 already widened.

- [ ] **Step 5: Confirm no table lost its rows**

```sql
select count(*) as tables, sum(row_count) as rows
from `teamster-332318.dagster_kippmiami_dlt_focus.__TABLES__`
```

Compare against the pre-cutover figures. A table at 0 rows that held rows before
means its reload failed — re-run that single table with the same run config.

- [ ] **Step 6: Watch 1 clean sensor tick**

Confirm `kippmiami__dlt__focus__intraday_sensor` produces a run that reaches
SUCCESS, and that `dbt build --select package:focus` is green against the
retyped tables.

---

## Rollback

Reverting the Dagster PR restores the narrow adapter, but the BigQuery tables
stay BIGNUMERIC, so `replace` then fails the other way: BIGNUMERIC to NUMERIC.
Recovery is the same manual run with `refresh: drop_resources` against the
reverted code. The dbt casts stay valid in both directions, because casting a
NUMERIC column to `numeric` is a no-op, so PR 1 never needs reverting.
