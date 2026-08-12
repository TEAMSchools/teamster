# DeansList Missing Assignments Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-point `rpt_deanslist__missing_assignments` off the pre-AY2627
`rpt_tableau__gradebook_assignments` view and onto the gradebook audit's
assignment model, so DeansList and the audit dashboard agree on what a missing
assignment is.

**Architecture:** Three changes in dependency order. First, project three label
columns on `int_powerschool__gradebook_assignments_scores` that already exist
inside its `base_powerschool__course_enrollments` join. Second, rewrite the
DeansList feed to read that model with the audit's own filters. Third, disable
the now-unreferenced legacy Tableau view.

**Tech Stack:** dbt (BigQuery), `uv` for all Python and dbt invocations, trunk
for lint, Dagster for the outbound extract (untouched by this plan).

Spec:
[`docs/superpowers/specs/2026-08-12-deanslist-missing-assignments-lineage-design.md`](../specs/2026-08-12-deanslist-missing-assignments-lineage-design.md).
Issue: [#4849](https://github.com/TEAMSchools/teamster/issues/4849).

## Global Constraints

- Worktree is
  `/workspaces/teamster/.worktrees/claude-deanslist-missing-assignments`, branch
  `GabyRangelB/fix/claude-deanslist-missing-assignments-lineage`. Every `git`
  call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`.
- Never bare `python` / `dbt`. Always `uv run`.
- `--target prod` dbt runs are forbidden. Use `--target dev` with `--defer`.
- `--state` must be the ABSOLUTE main-repo path
  `/workspaces/teamster/src/dbt/kipptaf/target/prod` — the relative form
  resolves under the worktree, which has no `target/prod`.
- `models/extracts/` inherits `+contract: enforced: true`, so every projected
  column needs a `data_type` entry in the properties yml or the build fails.
- Staging: name files explicitly in `git add`. Do not use `-A` or `.`.
- Do not run `trunk fmt`. The pre-commit hook formats; run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  from inside the worktree before pushing.
- `is_expected_missing` is `int64`, not boolean. Filter `= 1`.
- Retiring a model is always `enabled: false`. Never delete, never `drop view`.

---

## Task 0: Worktree setup

**Files:** none modified.

**Interfaces:**

- Consumes: nothing.
- Produces: a worktree that can run dbt.

- [ ] **Step 1: Install dbt packages**

A fresh worktree has no `dbt_packages/`, so every later build would fail with "N
package(s) specified in packages.yml, but only 0 package(s) installed".

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf
```

Expected: "Installing dbt-labs/dbt_utils" and similar, ending in "Installed from
version ...".

- [ ] **Step 2: Confirm the prod manifest exists for `--defer`**

```bash
ls -la /workspaces/teamster/src/dbt/kipptaf/target/prod/manifest.json
```

Expected: the file exists. If it is missing or stale, regenerate it:

```bash
uv run dbt parse --target prod --project-dir /workspaces/teamster/src/dbt/kipptaf --target-path target/prod
```

---

## Task 1: Project label columns on the assignments model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`

**Interfaces:**

- Consumes: `base_powerschool__course_enrollments` (aliased `e` in the model's
  `scores` CTE), which already carries `students_student_number` (`int64`),
  `courses_course_name` (`string`) and `teacher_lastfirst` (`string`).
- Produces: three new columns on `int_powerschool__gradebook_assignments_scores`
  — `student_number` (`int64`), `course_name` (`string`), `teacher_name`
  (`string`). Task 2 selects all three by these exact names.

- [ ] **Step 1: Add the three columns to the `scores` CTE**

In the `scores` CTE, immediately after the existing
`e.courses_credittype as credit_type,` line, add:

```sql
            e.students_student_number as student_number,
            e.courses_course_name as course_name,
            e.teacher_lastfirst as teacher_name,
```

- [ ] **Step 2: Carry them through the `assignment_coding` CTE**

`assignment_coding` enumerates its columns explicitly rather than using
`select *`, so a column added only to `scores` is silently dropped. After its
existing `credit_type,` line, add:

```sql
            student_number,
            course_name,
            teacher_name,
```

The final `select *, ...` then picks them up with no further change.

- [ ] **Step 3: Add the three columns to the properties yml**

Add these entries to the `columns:` list, following the file's existing pattern
of `data_type` plus source metadata. Place them after the `credit_type` entry:

```yaml
- name: student_number
  data_type: int64
  description:
    Student number of the student the assignment row belongs to. Carried through
    from the course-enrollment join so consumers do not re-derive it.
  config:
    meta:
      source_system: PowerSchool
      source_model: base_powerschool__course_enrollments
      source_column: students_student_number
- name: course_name
  data_type: string
  description: Name of the course the assignment's section belongs to.
  config:
    meta:
      source_system: PowerSchool
      source_model: base_powerschool__course_enrollments
      source_column: courses_course_name
- name: teacher_name
  data_type: string
  description: Teacher of record for the assignment's section, last-first.
  config:
    meta:
      source_system: PowerSchool
      source_model: base_powerschool__course_enrollments
      source_column: teacher_lastfirst
```

The formatter renders that block at top-level indentation. These are list items
under the model's `columns:` key, so indent each one to match the sibling
entries already in the file (six spaces before `- name:`) rather than pasting it
flat.

- [ ] **Step 4: Build the model and confirm the columns land**

```bash
uv run dbt build --select int_powerschool__gradebook_assignments_scores \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS on the model plus its `dbt_utils.unique_combination_of_columns`
test on `(_dbt_source_project, assignmentsectionid, students_dcid)`.

- [ ] **Step 5: Prove the addition changed no rows**

This is the load-bearing check for the task: the three columns come from a join
the model already had, so row counts must be identical to prod. Dev builds land
in `zz_<GITHUB_USER>_kipptaf_powerschool` — adjust the schema below if yours
differs.

```sql
select
    (
        select count(*)
        from `teamster-332318.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
        where academic_year = 2025
    ) as prod_rows,
    (
        select count(*)
        from `teamster-332318.zz_GabyRangelB_kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
        where academic_year = 2025
    ) as dev_rows
```

Expected: both counts equal, at 3,975,970 for AY2025 across all four regions. If
dev is higher, the join was altered rather than merely projected — revert and
re-read Step 1.

- [ ] **Step 6: Confirm the two downstream consumers are unaffected**

```bash
uv run dbt build --select int_powerschool__gradebook_assignment_scores_rollup fct_grades_assignments \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS on both, including `fct_grades_assignments`' contract. Both
project explicit column lists, so neither should notice the new columns. A
contract failure here means a `select *` was introduced somewhere — stop and
investigate rather than widening the contract.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml </dev/null
```

Expected: "No issues", or only `fmt` findings, which the commit hook fixes.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments add \
  src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql \
  src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments commit -m "feat(kipptaf): project student and course labels on gradebook assignment scores

Refs #4849"
```

---

## Task 2: Re-point the DeansList feed

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__missing_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__missing_assignments.yml`

**Interfaces:**

- Consumes: `int_powerschool__gradebook_assignments_scores` from Task 1 —
  specifically `student_number`, `course_name`, `teacher_name` (new in Task 1)
  plus the pre-existing `category_name` (`string`), `assignment_name`
  (`string`), `duedate` (`date`), `assignmentsectionid` (`int64`),
  `academic_year` (`int64`), `is_expected_missing` (`int64`), `school_level_alt`
  (`string`) and `_dbt_source_project` (`string`).
- Produces: a seven-column feed consumed by the Dagster extract asset
  `rpt_deanslist__missing_assignments` in
  `src/teamster/code_locations/kipptaf/extracts/config/deanslist-annual.yaml`.
  Column names must not change: `student_number`, `grade_category`,
  `assign_name`, `assign_date`, `course_name`, `teacher_name`, plus the new
  `assignmentsectionid`.

- [ ] **Step 1: Replace the model SQL**

The whole file becomes:

```sql
select
    student_number,
    assignmentsectionid,
    category_name as grade_category,
    assignment_name as assign_name,
    duedate as assign_date,
    course_name,
    teacher_name,
from {{ ref("int_powerschool__gradebook_assignments_scores") }}
where
    academic_year = {{ var("current_academic_year") }}
    and is_expected_missing = 1
    and _dbt_source_project != 'kippmiami'
    and school_level_alt != 'ES'
```

Note what is deliberately absent: no `finalgrade_category = 'Q'` (it existed
only to collapse the storecode fan-out, and per-assignment rows carry no
storecode), and no enrollment-window or dropped-section guard (both live inside
the upstream model's join now).

- [ ] **Step 2: Replace the properties yml**

The contract needs all seven columns. The whole file becomes:

```yaml
models:
  - name: rpt_deanslist__missing_assignments
    description: >-
      Assignments marked missing for students, fed to DeansList for follow-up.
      One row per student per assignment. Uses the gradebook audit's
      is_expected_missing definition, so exempt assignments and assignments not
      counted in the final grade are excluded. Miami is out of scope (off
      DeansList, gradebook on Focus) and ES is out of scope (no PowerSchool
      assignments; EOQ comments only).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - assignmentsectionid
          config:
            severity: error
    columns:
      - name: student_number
        data_type: int64
      - name: assignmentsectionid
        data_type: int64
        description:
          Assignment-section identifier. Projected so the uniqueness test has a
          key; DeansList ignores it.
      - name: grade_category
        data_type: string
      - name: assign_name
        data_type: string
      - name: assign_date
        data_type: date
      - name: course_name
        data_type: string
      - name: teacher_name
        data_type: string
```

- [ ] **Step 3: Build against the current year and expect zero rows**

```bash
uv run dbt build --select rpt_deanslist__missing_assignments \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS, and the uniqueness test PASSES vacuously.
`current_academic_year` is 2026 and no AY2026 assignments exist yet, so the view
is empty. **An empty build is not validation** — Step 4 is what actually tests
the logic.

- [ ] **Step 4: Rebuild against AY2025 to validate the logic**

```bash
uv run dbt build --select rpt_deanslist__missing_assignments \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --vars '{current_academic_year: 2025}'
```

Expected: PASS including the uniqueness test on real rows.

- [ ] **Step 5: Check the row count and region split**

The feed does not project a region column, so join back to the upstream to split
by region. Substitute your dev schema for `zz_GabyRangelB_kipptaf_extracts`.

```sql
select
    s._dbt_source_project,
    count(*) as feed_rows,
from `teamster-332318.zz_GabyRangelB_kipptaf_extracts.rpt_deanslist__missing_assignments`
as f
inner join
    `teamster-332318.zz_GabyRangelB_kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
    as s
    on f.assignmentsectionid = s.assignmentsectionid
    and f.student_number = s.student_number
group by 1
order by 1
```

Both sides must be the DEV copies. Prod `_scores` has no `student_number` until
this change merges, so joining to prod fails with an unrecognized-name error.

Expected, matching the spec's Expected output table exactly:

| `_dbt_source_project` | rows    |
| --------------------- | ------- |
| kippcamden            | 66,340  |
| kippnewark            | 139,704 |
| kipppaterson          | 3,267   |

Total 209,311. No `kippmiami` row. If Paterson is absent, the re-point did not
take and the model is still reading the legacy view. If Miami appears, the
filter is missing.

- [ ] **Step 6: Confirm no null labels**

The label columns come through an inner join, so nulls would indicate a real
upstream gap rather than a join miss.

```sql
select
    countif(student_number is null) as null_student_number,
    countif(course_name is null) as null_course_name,
    countif(teacher_name is null) as null_teacher_name,
    countif(grade_category is null) as null_grade_category,
    countif(assign_name is null) as null_assign_name,
    countif(assign_date is null) as null_assign_date,
from `teamster-332318.zz_GabyRangelB_kipptaf_extracts.rpt_deanslist__missing_assignments`
```

Expected: zero for `student_number`, `assign_name` and `assign_date`. A non-zero
`course_name`, `teacher_name` or `grade_category` is worth reporting to the
requester before proceeding — it means PowerSchool is missing section metadata,
which the legacy feed would have shown as a blank too.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__missing_assignments.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__missing_assignments.yml </dev/null
```

Expected: "No issues", or only `fmt` findings.

- [ ] **Step 8: Commit**

```bash
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments add \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__missing_assignments.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__missing_assignments.yml
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments commit -m "fix(kipptaf): read the DeansList missing-assignments feed from the audit lineage

Adds Paterson, drops Miami and ES, and adopts the audit's is_expected_missing
definition. Refs #4849"
```

---

## Task 3: Disable the legacy Tableau view

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_assignments.yml`

**Interfaces:**

- Consumes: nothing. Task 2 removed the last `ref()` to this model.
- Produces: nothing. This is a retirement.

- [ ] **Step 1: Confirm nothing references it any more**

```bash
grep -rn "rpt_tableau__gradebook_assignments" \
  --include='*.sql' --include='*.yml' --include='*.yaml' --include='*.py' \
  /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src | grep -v "/target/"
```

Expected: exactly one hit, the `- name:` line in the model's own properties yml.
If `rpt_deanslist__missing_assignments.sql` still appears, Task 2 is incomplete
— stop.

- [ ] **Step 2: Add the config block**

Insert `config:` directly under the model `name:`, so the file begins:

```yaml
models:
  - name: rpt_tableau__gradebook_assignments
    config:
      enabled: false
    columns:
```

Leave the whole `columns:` list and the `.sql` file untouched. The model carries
no data tests, so nothing else needs `enabled: false`. Do not drop the prod
BigQuery view.

- [ ] **Step 3: Confirm dbt now treats it as disabled**

```bash
uv run dbt ls --select rpt_tableau__gradebook_assignments \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev 2>&1 | grep '^kipptaf' || echo "not selected (disabled) — expected"
```

Expected: "not selected (disabled)". A returned node name means the config
landed in the wrong place in the yml.

- [ ] **Step 4: Confirm the graph still parses with the model gone**

```bash
uv run dbt parse --no-partial-parse \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev
```

Expected: clean parse. A "depends on a node named ... which was not found" error
means something still refs it — return to Step 1.

- [ ] **Step 5: Lint**

```bash
cd /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_assignments.yml </dev/null
```

Expected: "No issues", or only `fmt` findings.

- [ ] **Step 6: Commit**

```bash
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments add \
  src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__gradebook_assignments.yml
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments commit -m "chore(kipptaf): disable the legacy gradebook assignments view

Its last consumer moved to the audit lineage. Refs #4849"
```

---

## Task 4: Whole-branch verification and PR

**Files:** none modified.

**Interfaces:**

- Consumes: Tasks 1 through 3.
- Produces: a pushed branch and an open PR referencing #4849.

- [ ] **Step 1: Build the full affected chain in one pass**

```bash
uv run dbt build --select int_powerschool__gradebook_assignments_scores+ \
  --project-dir /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments/src/dbt/kipptaf \
  --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: every model PASSES. Pre-existing warn-level test failures unrelated to
these three models are acceptable — confirm each also warns on prod before
dismissing it.

- [ ] **Step 2: Lint every changed file**

```bash
cd /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git diff --name-only origin/main...HEAD | grep -v '^docs/') </dev/null
```

Expected: "No issues".

- [ ] **Step 3: Review the branch diff**

```bash
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments diff --stat origin/main...HEAD
```

Expected: exactly six files — the spec, the plan, and the four model/properties
files from Tasks 1 through 3. Nothing under `src/dbt/CLAUDE.md`; that rule was
moved to the CARAT branch deliberately.

- [ ] **Step 4: Request review**

Invoke the `superpowers:requesting-code-review` skill before opening the PR.

- [ ] **Step 5: Push and open the PR**

Ask the requester before pushing. Use `.github/pull_request_template.md` as the
PR body and include `Closes #4849`.

```bash
git -C /workspaces/teamster/.worktrees/claude-deanslist-missing-assignments push -u origin \
  GabyRangelB/fix/claude-deanslist-missing-assignments-lineage
```

- [ ] **Step 6: Report the residual manual step**

Tell the requester in the PR body and in conversation: the prod BigQuery view
`kipptaf_tableau.rpt_tableau__gradebook_assignments` remains, by design. It
stops refreshing once this merges. No `drop view` is issued.

## Post-merge watch

Not a task, but flag it to the requester: the DeansList extract runs nightly at
1:25am Eastern and the feed stays empty until teachers enter AY2026 assignments.
Nobody has confirmed how DeansList treats an empty file. If it deletes prior
records, that behavior is unchanged by this plan but worth knowing before the
first post-merge run.
