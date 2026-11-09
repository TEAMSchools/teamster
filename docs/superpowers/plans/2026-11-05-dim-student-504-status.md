# dim_student_504_status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 504 status SCD2 dim, roll `is_504` into
`dim_student_enrollment_status`, and expose it on the 3 student Cube views so
DDI Suite and the other dashboards can slice by 504.

**Architecture:** `dim_student_504_status` copies the Miami `pm_leg` shape of
`dim_student_ell_status`: 1 span per enrollment stint where
`int_students__student_enrollments.is_504` is true, no source dates. The rollup
left-joins it and coalesces to false. A separate Cube PR adds the dimension
after the dbt PR builds in prod; a validation comparison proves it against DDI
Suite's `status_504`.

**Tech Stack:** dbt (BigQuery), Cube YAML, pytest (`tests/cube/`),
`scripts/cube_validation`.

**Spec:** [#6284](https://github.com/TEAMSchools/teamster/issues/6284), the "For
Claude" section.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-504-status-dim`,
  branch `cristinabaldor/feat/claude-504-status-dim`. Absolute paths and
  `git -C` on every call.
- PR bodies say `Refs #6284`, never `Closes`: the issue outlives the dbt PR.
- Hash keys through the macros in `src/dbt/kipptaf/macros/entity_keys.sql` (A7):
  `{{ student_key("student_number") }}` and
  `{{ student_enrollment_key("student_number", "_dbt_source_project", "academic_year", "entrydate") }}`.
  The PK has no macro: `dbt_utils.generate_surrogate_key`.
- Tag every new `is_504` column `config.meta.contains_pii: true`. Do not tag or
  retag other columns.
- GitHub text carries counts only; counts under 10 read `<10`.
- `uv run` for every dbt and pytest call. `--target dev` only; staging and prod
  writes go to the user.
- Before each push:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree.

## Review Focus

1. Two 504 stints with the same student, region, and `entrydate` (2 schools, 1
   day) collide on `student_504_status_key`. The PK `unique` test fails the
   build. Prod count at plan time: 0.
2. A zero-day stint (`exitdate = entrydate`) gives an end before its start. Prod
   count at plan time: 0. Task 1 step 4 checks it.
3. Miami's unset (null) `is_504` must read `false` in the rollup, not null. Task
   2 step 3 checks it.
4. Graduate placeholders (null `entrydate`) must not reach the dim. The `where`
   filter does this; Task 1 step 4 counts it.
5. A Cube query sliced by `is_504` cannot use the `proficiency_rollup`
   pre-aggregation, which does not carry `is_504`, so it reads the raw fact.
   Task 4 step 5 records the `dry_run` result. Adding `is_504` to the rollup is
   out of scope.

---

### Task 1: `dim_student_504_status` mart, overlap test, exposure entries

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_student_504_status.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_504_status.yml`
- Create:
  `src/dbt/kipptaf/tests/dim_student_504_status__no_overlapping_spans.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml` (entry after
  `dim_student_ell_status__no_overlapping_spans`, line 204)
- Modify: `src/dbt/kipptaf/models/exposures/cube.yml:46-48`

**Interfaces:**

- Produces: `dim_student_504_status` with columns `_dbt_source_project`
  (string), `effective_date_start_key` (date), `effective_date_end_key` (date),
  `student_504_status_key` (string, PK), `student_key` (string),
  `student_enrollment_key` (string), `is_504` (boolean, always true),
  `is_current` (boolean). At most 1 row per `student_enrollment_key`.

- [ ] **Step 1: Write the overlap test**

Copy `tests/dim_student_ell_status__no_overlapping_spans.sql` with the ref
swapped to `dim_student_504_status`. Add the `tests/properties.yml` entry with
`config: severity: error` and a description: within a `student_key` and
district, 504 spans must not overlap; an overlap means 2 concurrent stints both
carry the 504 flag.

- [ ] **Step 2: Write `dim_student_504_status.sql`**

1 CTE reads `int_students__student_enrollments`:

- `where is_504 and entrydate is not null` (`is_504` is null in Miami when
  unset; `where is_504` drops null and false alike).
- `entrydate as effective_date_start`.
- `coalesce(date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)) as effective_date_end`
  with the ELL dim's half-open comment.

The final select matches the ELL dim's order and shapes, using the macros from
_Global Constraints_ for `student_key` and `student_enrollment_key`, and
`true as is_504`.

- [ ] **Step 3: Write the properties YAML**

Copy `properties/dim_student_ell_status.yml` and change:

- Model description: SCD2 504 plan status per student per district. 1 span per
  enrollment stint whose 504 flag is set; no source carries 504 begin or end
  dates, so each span covers the whole stint. Inclusion-based: consumers default
  to false when no row covers the date. NJ past stints carry a per-stint value;
  the current NJ stint and every Miami stint carry the student's current value.
  Keep it source-agnostic: field names go in `config.meta.source_column`, not
  the description.
- Tests: `unique` on `student_504_status_key`, `not_null` on
  `_dbt_source_project`. No other column tests: the SQL guarantees `is_504`,
  `is_current`, and both date keys are non-null (`.claude/rules/dbt-yaml.md`,
  _Choosing a test_).
- `is_504` gets `config.meta.contains_pii: true` and a description saying it is
  true on every row.
- Date-key descriptions: start is the stint's entry date; end is the day before
  exit, `9999-12-31` while the stint is open.
- Keep the `config.meta.foreign_key` blocks and the `dagster` meta with
  `asset_key: [kipptaf, marts, dim_student_504_status]`.

- [ ] **Step 4: Add both status marts to the Cube exposure**

In `cube.yml` `cube_semantic_layer.depends_on`, add
`ref("dim_student_504_status")` and `ref("dim_student_enrollment_status")`
beside the other status dims. The second one has been missing; every mart
belongs in that list.

- [ ] **Step 5: Build into dev**

Invoke `dbt-local-dev` first. Then, in separate Bash calls:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-504-status-dim/src/dbt/kipptaf
uv run dbt build --select dim_student_504_status+ --project-dir /workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-504-status-dim/src/dbt/kipptaf <dev and defer flags from dbt-local-dev> 2>&1 | tail -n 30
```

Expected: model OK, `unique` PASS, `not_null` PASS, overlap test PASS.

- [ ] **Step 6: Check the dev rows against the source**

Run read-only against the dev schema (`zz_<user>_kipptaf_marts`):

```sql
select
    count(*) as n_rows,
    count(distinct student_enrollment_key) as n_enrollment_keys,
    countif(effective_date_end_key < effective_date_start_key) as n_end_before_start,
from `teamster-332318.zz_<user>_kipptaf_marts.dim_student_504_status`
```

Expected: `n_rows = n_enrollment_keys`; `n_end_before_start = 0`; `n_rows`
equals `countif(is_504 and entrydate is not null)` over
`kipptaf_students.int_students__student_enrollments` (1,926 at plan time).

- [ ] **Step 7: Commit**

```bash
git -C <worktree> add src/dbt/kipptaf/models/marts/dimensions/dim_student_504_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_504_status.yml src/dbt/kipptaf/tests/dim_student_504_status__no_overlapping_spans.sql
git -C <worktree> add -u
git -C <worktree> commit -m "feat(dbt): add dim_student_504_status"
```

### Task 2: Roll `is_504` into `dim_student_enrollment_status`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollment_status.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollment_status.yml`

**Interfaces:**

- Consumes: `dim_student_504_status.student_enrollment_key`, `.is_504` (Task 1).
- Produces: `dim_student_enrollment_status.is_504` (boolean, never null). Task 4
  twins its description.

- [ ] **Step 1: Edit the SQL**

Add a CTE `section_504` after `ell`, with the comment
`-- 504: at most one span per stint; LEFT JOIN returns NULL when absent.`,
selecting `student_enrollment_key, is_504` from `dim_student_504_status`.
Left-join it, aliased `s5`, to `enr` on `student_enrollment_key`, and add
`coalesce(s5.is_504, false) as is_504` after `is_ell` in the boolean block.

- [ ] **Step 2: Edit the YAML**

Add `is_504` after `is_ell`, with `data_type: boolean`,
`config.meta.contains_pii: true`, and this description, verbatim (Task 4 copies
it):

```text
TRUE if the student had a Section 504 plan during this enrollment stint.
FALSE when no 504 record covers the stint, including when the source system
leaves the flag unset, as it does for most Miami students and every
current-year Paterson student. This is the enrollment 504 status the
assessment dashboards show; state test files carry their own 504 flag, which
can differ.
```

Add 504 to the model description's list of rolled-up statuses ("ELL, IEP, 504,
and meal eligibility"; "504 via LEFT JOIN (one span per stint)").

- [ ] **Step 3: Build and check equality**

```bash
uv run dbt build --select dim_student_enrollment_status --project-dir /workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-504-status-dim/src/dbt/kipptaf <dev and defer flags> 2>&1 | tail -n 30
```

Then run read-only:

```sql
with expected as (
    select
        to_hex(md5(concat(
            cast(student_number as string), '-', _dbt_source_project, '-',
            cast(academic_year as string), '-', cast(entrydate as string)
        ))) as student_enrollment_key,
        coalesce(is_504, false) as is_504,
    from `teamster-332318.kipptaf_students.int_students__student_enrollments`
    where entrydate is not null
)

select
    count(*) as n_rows,
    countif(s.is_504 is null) as n_null,
    countif(s.is_504 != coalesce(e.is_504, false)) as n_mismatch,
    countif(s.is_504) as n_true,
from `teamster-332318.zz_<user>_kipptaf_marts.dim_student_enrollment_status` as s
left join expected as e on s.student_enrollment_key = e.student_enrollment_key
```

Expected: `n_null = 0`, `n_mismatch = 0`, `n_true` equals Task 1's `n_rows`, and
`n_rows` equals the prod `kipptaf_marts.dim_student_enrollment_status` row count
(no fan-out).

- [ ] **Step 4: Commit**

```bash
git -C <worktree> add -u
git -C <worktree> commit -m "feat(dbt): add is_504 to dim_student_enrollment_status"
```

### Task 3: Lint, push, open the dbt PR

**Files:** none new.

- [ ] **Step 1: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/marts/dimensions/dim_student_504_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_504_status.yml src/dbt/kipptaf/tests/dim_student_504_status__no_overlapping_spans.sql src/dbt/kipptaf/tests/properties.yml src/dbt/kipptaf/models/exposures/cube.yml src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollment_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollment_status.yml docs/superpowers/plans/2026-11-05-dim-student-504-status.md </dev/null
```

Expected: no findings. Fix any and amend the relevant commit.

- [ ] **Step 2: Push and open the PR**

`git -C <worktree> push -u origin cristinabaldor/feat/claude-504-status-dim`,
then `mcp__github__create_pull_request` against `main` with a body from
`.github/pull_request_template.md`: what changed, the Task 1 step 6 and Task 2
step 3 results as counts, and `Refs #6284`. Check the returned title and body.

- [ ] **Step 3: Offer CI watch and review response**

Per the root CLAUDE.md _Pull requests and CI_: offer both; on a yes, invoke
`pr-ci-review` and arm a Monitor in that turn. Run the marts pre-merge checklist
(`src/dbt/kipptaf/models/marts/CLAUDE.md`) before the final PR comment.

### Task 4: Cube PR (after the dbt PR merges and builds in prod)

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollment_status.yml` (after
  `is_ell`, line 12)
- Modify: `tests/cube/test_cube_schema.py` (`TWINS.update`, line 520)
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`
  (`includes` line 130, `Status` folder line 280)
- Modify:
  `src/cube/model/views/students/student_attendance_enrollment_daily_view.yml`
  (`includes` line 153 and its `Status` folder)
- Modify:
  `src/cube/model/views/students/student_attendance_enrollment_periods_view.yml`
  (`includes` line 120, `Status` folder line 195)

**Interfaces:**

- Consumes: `kipptaf_marts.dim_student_enrollment_status.is_504` in prod; its
  YAML description (Task 2 step 2).
- Produces: `student_enrollment_status.is_504` on the 3 views (prefixed
  `student_enrollment_status_is_504` where the view prefixes; check each view's
  `prefix:` setting).

- [ ] **Step 1: Branch**

Ask the user worktree or branch switch, per root CLAUDE.md _Before you start_.
Create `cristinabaldor/feat/claude-504-status-cube` from `origin/main` with the
no-issue form. Read `.claude/rules/cube-authoring.md` and `src/cube/CLAUDE.md`.

- [ ] **Step 2: Write the failing twin test**

Add
`("student_enrollment_status", "is_504"): ("dim_student_enrollment_status", "is_504")`
to `TWINS`. Run `npm ci` in the worktree's `src/cube`, then
`uv run pytest tests/cube/test_cube_schema.py -k twin`. Expected: FAIL, member
`is_504` missing.

- [ ] **Step 3: Add the dimension and view entries**

Dimension: `name: is_504`, `sql: is_504`, `type: boolean`, `public: true`,
`description:` equal to the dbt description. Add `is_504` after `is_ell` in each
view's `includes` and `Status` folder.

- [ ] **Step 4: Run the Cube tests**

`uv run pytest tests/cube/` from the worktree. Expected: PASS.

- [ ] **Step 5: Smoke-test locally**

Follow `cube-builder` _Build_ step 2 (`CUBEJS_SCHEMA_PATH` copy, local server).
The prod mart has the column now, so no `zz_` redirect. `load`
`student_assessment_scores_view` count of students by `is_504` for the current
academic year; `dry_run` the same query and record whether it hits a
pre-aggregation (Review Focus 5).

- [ ] **Step 6: Commit, lint, push, PR**

Commit `feat(cube): expose is_504 on student enrollment status`, run the trunk
check on the 4 YAML files and the test file, push, open the PR with `Refs #6284`
and the step 5 counts.

### Task 5: Validate against DDI Suite

**Files:**

- Modify: `src/cube/validation/student_assessment_scores_view.yml` on the DDI
  Suite validation branch (`cube-builder` _Build_: base it on the branch
  carrying the validator).

- [ ] **Step 1: Add the comparison**

Invoke `cube-validation`. Add a comparison that slices an existing student count
measure on `student_assessment_scores_view` by
`student_enrollment_status_is_504`, mapped under `dims` to DDI Suite's
`status_504` (`Has 504` = true, `No 504` = false), with a `rows:` block. Read
the view's validation file for that measure's known causes first.

- [ ] **Step 2: Run the runbook**

`cube-validation` runbook steps 4 to 7: `prove`, `check-api`, `prove --check`,
`run`. Expected: match within tolerance. A difference traced to STAT's
state-file flag or Newark's current-year source is a known cause from #6284, not
a bug in this field.

- [ ] **Step 3: Report**

Put the `Cube:` and `Fact:` lines `run` printed in the Cube PR description. With
the analyst's approval, propose the Asana subtask move ("504 status",
gid 1219761127051890) as far as the result supports.
