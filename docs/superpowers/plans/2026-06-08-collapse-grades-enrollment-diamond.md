# Collapse `fct_grades_*` → `dim_student_enrollments` Diamond — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the diamond path by dropping the direct
`student_enrollment_key` FK from `fct_grades_assignments` and `fct_grades_term`,
after fixing `dim_student_section_enrollments` so its `student_enrollment_key`
resolves for every section that overlaps a school enrollment stint.

**Architecture:** Change the dim's enrollment match from a point anchor on
`cc_dateenrolled` to an overlap match against enrollment stints, collapsing the
rare (147) multi-stint fan-out with a covering-first deterministic pick. Then
remove the facts' independently-computed direct FK; consumers traverse
`student_section_enrollment_key` → `dim_student_section_enrollments` →
`student_enrollment_key`. A `warn` test monitors multi-stint drift.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, the kipptaf project. Spec:
[2026-06-08-collapse-grades-enrollment-diamond-design.md](../specs/2026-06-08-collapse-grades-enrollment-diamond-design.md).
Issues: [#4145](https://github.com/TEAMSchools/teamster/issues/4145) (this
work), [#4146](https://github.com/TEAMSchools/teamster/issues/4146) (separate
DQ).

---

## Conventions for every task

- All paths are relative to the worktree root
  `/workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond`.
- Run dbt from the main repo with `--project-dir` pointing at the worktree, and
  defer to prod for unstaged externals (the `reporting__terms` Google Sheet):

  ```bash
  uv run dbt deps --project-dir \
    /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf
  ```

  (run `dbt deps` once — a fresh worktree has no `dbt_packages/`).

- Build/show commands use this prefix (the `--state` path must be absolute from
  a worktree):

  ```bash
  uv run dbt build --project-dir \
    /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
    --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
    --select <model>
  ```

- `git` calls use `git -C <worktree>`.
- Commit messages use conventional commits and end with the
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
  trailer.
- `<dev_schema>` below = the schema your dbt profile writes to locally
  (`kipptaf_marts` mapped through your dev target). Final PR verification runs
  against the dbt Cloud PR-branch schema `dbt_cloud_pr_<job>_<pr>_marts`.

---

### Task 1: Rewrite `dim_student_section_enrollments` to resolve by overlap

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml`

- [ ] **Step 1: Replace the model SQL**

Replace the entire contents of `dim_student_section_enrollments.sql` with:

```sql
with
    student_enrollments as (
        select
            _dbt_source_project,
            studentid,
            schoolid,
            yearid,
            student_number,
            academic_year,
            entrydate,
            exitdate,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_overlap as (
        select
            cc._dbt_source_project,
            cc.cc_dcid,
            cc.sections_dcid,
            cc.cc_academic_year,
            cc.cc_dateenrolled,
            cc.cc_dateleft,
            cc.cc_abs_termid,
            cc.sections_schoolid,
            cc.region,
            cc.is_dropped_section,
            cc.is_dropped_course,

            enr._dbt_source_project as enr_source_project,
            enr.student_number as enr_student_number,
            enr.academic_year as enr_academic_year,
            enr.entrydate as enr_entrydate,

            (
                cc.cc_dateenrolled >= enr.entrydate
                and cc.cc_dateenrolled < enr.exitdate
            ) as is_covering,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        left join
            student_enrollments as enr
            on cc.cc_studentid = enr.studentid
            and cc.sections_schoolid = enr.schoolid
            and cc.cc_yearid = enr.yearid
            and cc._dbt_source_project = enr._dbt_source_project
            and enr.entrydate < cc.cc_dateleft
            and enr.exitdate > cc.cc_dateenrolled
    ),

    enrollment_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_overlap",
                partition_by="cc_dcid, _dbt_source_project",
                order_by="is_covering desc, enr_entrydate asc",
            )
        }}
    ),

    course_enrollments_joined as (
        select
            er.cc_dcid,
            er._dbt_source_project,
            er.sections_dcid,
            er.cc_academic_year,
            er.cc_dateenrolled,
            er.cc_dateleft,
            er.is_dropped_section,
            er.is_dropped_course,
            er.enr_source_project,
            er.enr_student_number,
            er.enr_academic_year,
            er.enr_entrydate,

            rt.`type` as rt_type,
            rt.code as rt_code,
            rt.name as rt_name,
            rt.start_date as rt_start_date,
            rt.region as rt_region,
            rt.school_id as rt_school_id,
        from enrollment_resolved as er
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on er.cc_abs_termid = rt.powerschool_term_id
            and er.sections_schoolid = rt.school_id
            and er.region = rt.region
            and rt.`type` = 'RT'
    )

select
    cc_academic_year as academic_year,
    cc_dateenrolled as entry_date,
    cc_dateleft as exit_date,
    is_dropped_section,
    is_dropped_course,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
    as student_section_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["sections_dcid", "_dbt_source_project"]) }}
    as course_section_key,

    if(
        enr_student_number is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "enr_student_number",
                    "enr_source_project",
                    "enr_academic_year",
                    "enr_entrydate",
                ]
            )
        }},
        cast(null as string)
    ) as student_enrollment_key,

    if(
        rt_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt_type",
                    "rt_code",
                    "rt_name",
                    "rt_start_date",
                    "rt_region",
                    "rt_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from course_enrollments_joined
```

- [ ] **Step 2: Update the `student_enrollment_key` column description**

In `dim_student_section_enrollments.yml`, replace the `student_enrollment_key`
column `description` text:

```yaml
- name: student_enrollment_key
  data_type: string
  description: >-
    Surrogate key derived from student_number, _dbt_source_project,
    academic_year, and entrydate. FK to dim_student_enrollments. Resolved to the
    school enrollment stint the section enrollment overlaps (the stint covering
    cc_dateenrolled when one exists, else the earliest overlapping stint). Null
    only when no enrollment stint overlaps the section enrollment.
```

(Leave the constraint and `relationships` test blocks unchanged.)

- [ ] **Step 3: Build the dim and its upstreams**

Run:

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select dim_student_section_enrollments
```

Expected: PASS — model builds, `unique` + `not_null` on
`student_section_enrollment_key` pass, `relationships` on
`student_enrollment_key` passes.

- [ ] **Step 4: Verify NULL fill and PK uniqueness against the built relation**

Run this against `<dev_schema>` (the schema the build wrote to). Use the
BigQuery MCP:

```sql
select
  count(*) as n_rows,
  count(distinct student_section_enrollment_key) as n_distinct_pk,
  countif(student_enrollment_key is null) as n_enrollment_null,
from `teamster-332318.<dev_schema>.dim_student_section_enrollments`
```

Expected: `n_rows = n_distinct_pk` (PK intact). `n_enrollment_null` ≈ 2,541
(down from ~22K under the old point match — the orphan floor).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  add src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql \
      src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  commit -m "refactor(marts): resolve dim_student_section_enrollments enrollment by overlap

Refs #4145

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add the multi-stint-overlap `warn` test

**Files:**

- Create:
  `src/dbt/kipptaf/tests/dim_student_section_enrollments__no_multi_stint_overlap.sql`
- Modify: `src/dbt/kipptaf/tests/properties.yml`

- [ ] **Step 1: Create the test SQL**

Create `dim_student_section_enrollments__no_multi_stint_overlap.sql` with:

```sql
with
    student_enrollments as (
        select studentid, schoolid, yearid, entrydate, exitdate, _dbt_source_project
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where entrydate is not null and exitdate is not null
    )

select
    cc.cc_dcid,
    cc._dbt_source_project,
    count(*) as n_overlapping_stints,
from {{ ref("base_powerschool__course_enrollments") }} as cc
inner join
    student_enrollments as enr
    on cc.cc_studentid = enr.studentid
    and cc.sections_schoolid = enr.schoolid
    and cc.cc_yearid = enr.yearid
    and cc._dbt_source_project = enr._dbt_source_project
    and enr.entrydate < cc.cc_dateleft
    and enr.exitdate > cc.cc_dateenrolled
where not cc.is_dropped_section
group by cc.cc_dcid, cc._dbt_source_project
having count(*) > 1
```

- [ ] **Step 2: Register the test in `properties.yml`**

Append this entry under the top-level `data_tests:` list in
`src/dbt/kipptaf/tests/properties.yml` (no `severity:` — the project default is
`warn`, which is intended here):

```yaml
- name: dim_student_section_enrollments__no_multi_stint_overlap
  description: >-
    Warns when a non-dropped course-enrollment (cc) record overlaps more than
    one school enrollment stint. dim_student_section_enrollments resolves these
    to a single stint (covering-first, else earliest), so a nonzero count is a
    known, monitored condition (baseline ~147, almost all genuine mid-year
    drop/re-enroll) rather than a failure. Growth signals new boundary-spanning
    sections to review.
  config:
    meta:
      dagster:
        ref:
          name: dim_student_section_enrollments
```

- [ ] **Step 3: Run the test**

Run:

```bash
uv run dbt test --project-dir \
  /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select dim_student_section_enrollments__no_multi_stint_overlap
```

Expected: WARN (not error) reporting ~147 failing rows. A warn does not fail the
run.

- [ ] **Step 4: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  add src/dbt/kipptaf/tests/dim_student_section_enrollments__no_multi_stint_overlap.sql \
      src/dbt/kipptaf/tests/properties.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  commit -m "test(marts): warn on multi-stint section-enrollment overlap

Refs #4145

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Drop the direct FK from `fct_grades_assignments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml`

- [ ] **Step 1: Remove the `student_enrollment_key` SELECT expression**

In `fct_grades_assignments.sql`, delete this block from the `select` list (the
`student_enrollments` CTE and its inner join STAY — they filter the assignment
row population; add the trailing comment shown to record why):

Remove:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "asg.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,
```

Then add this comment immediately above the
`inner join student_enrollments as enr` line:

```sql
-- retained as a row-population filter (assignment must fall within a covering
-- school enrollment); enrollment linkage now flows via
-- student_section_enrollment_key -> dim_student_section_enrollments
```

- [ ] **Step 2: Remove the column from the contract YAML**

In `fct_grades_assignments.yml`, delete the entire `student_enrollment_key`
column entry (the column `name`, `data_type`, `description`, the `foreign_key`
constraint block, and the `not_null` + `relationships` `data_tests`):

```yaml
- name: student_enrollment_key
  data_type: string
  description: >-
    FK to dim_student_enrollments. Surrogate key derived from student_number,
    _dbt_source_project, academic_year, and entrydate.
  constraints:
    - type: foreign_key
      to: ref('dim_student_enrollments')
      to_columns: [student_enrollment_key]
      warn_unsupported: false
  data_tests:
    - not_null

    - relationships:
        arguments:
          to: ref('dim_student_enrollments')
          field: student_enrollment_key
```

- [ ] **Step 3: Update the model description**

In `fct_grades_assignments.yml`, change the model `description` FK sentence
from:

```yaml
FK to dim_student_section_enrollments, dim_student_enrollments, dim_terms, and
dim_dates (role-playing via due_date_key).
```

to:

```yaml
FK to dim_student_section_enrollments, dim_terms, and dim_dates (role-playing
via due_date_key). Reaches dim_student_enrollments by traversing
student_section_enrollment_key.
```

- [ ] **Step 4: Build and verify row count unchanged + traversal resolves**

Run:

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select fct_grades_assignments
```

Expected: PASS — `unique` (warn, per #3915) + `not_null` on
`grades_assignment_key`, `not_null` + `relationships` on
`student_section_enrollment_key`, all pass. No `student_enrollment_key` column
remains.

Then verify the traversal carries the enrollment and row count held (run against
`<dev_schema>`):

```sql
select
  count(*) as n_rows,
  countif(d.student_enrollment_key is null) as n_traversed_null,
from `teamster-332318.<dev_schema>.fct_grades_assignments` as f
left join `teamster-332318.<dev_schema>.dim_student_section_enrollments` as d
  on f.student_section_enrollment_key = d.student_section_enrollment_key
```

Expected: `n_rows` ≈ 25,410,721 (unchanged — the enr filter join was kept).
`n_traversed_null` ≈ 0 (down from 985,984; the leftover is the orphan floor).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  add src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql \
      src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  commit -m "refactor(marts): drop direct student_enrollment_key FK from fct_grades_assignments

Refs #4145

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Drop the direct FK from `fct_grades_term`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql`
- Modify: `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_term.yml`

- [ ] **Step 1: Remove the `student_enrollment_key` SELECT expression**

In `fct_grades_term.sql`, delete this block from the `select` list (the
`student_enrollments` CTE and its inner join STAY):

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "fg.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,
```

Then add this comment immediately above the
`inner join student_enrollments as enr` line:

```sql
-- retained as a row-population filter (term grade must fall within a covering
-- school enrollment); enrollment linkage now flows via
-- student_section_enrollment_key -> dim_student_section_enrollments
```

- [ ] **Step 2: Remove the column from the contract YAML**

In `fct_grades_term.yml`, delete the entire `student_enrollment_key` column
entry:

```yaml
- name: student_enrollment_key
  data_type: string
  description: >-
    FK to dim_student_enrollments. Surrogate key derived from student_number,
    _dbt_source_project, academic_year, and entrydate.
  constraints:
    - type: foreign_key
      to: ref('dim_student_enrollments')
      to_columns: [student_enrollment_key]
      warn_unsupported: false
  data_tests:
    - not_null

    - relationships:
        arguments:
          to: ref('dim_student_enrollments')
          field: student_enrollment_key
```

- [ ] **Step 3: Update the model description**

In `fct_grades_term.yml`, change the model `description` FK sentence from:

```yaml
FK to dim_student_section_enrollments, dim_student_enrollments, dim_terms, and
dim_dates (role-playing via term_start_date_key and term_end_date_key).
```

to:

```yaml
FK to dim_student_section_enrollments, dim_terms, and dim_dates (role-playing
via term_start_date_key and term_end_date_key). Reaches dim_student_enrollments
by traversing student_section_enrollment_key.
```

- [ ] **Step 4: Build and verify**

Run:

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select fct_grades_term
```

Expected: PASS — `unique` + `not_null` on `grades_term_key`, FK tests on
`student_section_enrollment_key` pass; no `student_enrollment_key` column.

Verify (against `<dev_schema>`):

```sql
select
  count(*) as n_rows,
  countif(d.student_enrollment_key is null) as n_traversed_null,
from `teamster-332318.<dev_schema>.fct_grades_term` as f
left join `teamster-332318.<dev_schema>.dim_student_section_enrollments` as d
  on f.student_section_enrollment_key = d.student_section_enrollment_key
```

Expected: `n_rows` ≈ 262,188 (unchanged). `n_traversed_null` ≈ 0 (down from 974;
the ~47 nonpositive-length term rows from #4146 may remain).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  add src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql \
      src/dbt/kipptaf/models/marts/facts/properties/fct_grades_term.yml
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  commit -m "refactor(marts): drop direct student_enrollment_key FK from fct_grades_term

Refs #4145

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Lint, full-chain build, and push for CI

**Files:** none (verification + push).

- [ ] **Step 1: Lint the changed SQL/YAML with trunk (from inside the
      worktree)**

Run (cwd must be the worktree; the binary lives in the main repo):

```bash
cd /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond && \
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql \
  src/dbt/kipptaf/tests/dim_student_section_enrollments__no_multi_stint_overlap.sql \
  src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql \
  src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql
```

Expected: no issues. If sqlfluff flags ST03 on `enrollment_overlap` despite the
`-- trunk-ignore` line, confirm the directive sits on the line immediately above
the CTE.

- [ ] **Step 2: Build the full downstream chain locally**

Run:

```bash
uv run dbt build --project-dir \
  /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond/src/dbt/kipptaf \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --select dim_student_section_enrollments+ fct_grades_assignments fct_grades_term
```

Expected: PASS (the multi-stint test WARNs at ~147; everything else passes).

- [ ] **Step 3: Push the branch (hand to the user if the classifier blocks)**

```bash
git -C /workspaces/teamster/.worktrees/cbini/refactor/claude-grades-enrollment-diamond \
  push -u origin cbini/refactor/claude-grades-enrollment-diamond
```

- [ ] **Step 4: Open the PR**

Use the GitHub MCP `create_pull_request` with base `main`, head
`cbini/refactor/claude-grades-enrollment-diamond`, body from
`.github/pull_request_template.md`, and `Closes #4145` in the body.

- [ ] **Step 5: After dbt Cloud CI passes, verify against the PR-branch schema**

Resolve `<job>` from `mcp__dbt__get_job_run_details` and run the four spec
verification queries against `dbt_cloud_pr_<job>_<pr>_marts`:

1. NULL linkage → ~0 for both facts (divergence query, `traversal NULL` bucket).
2. Stint-mismatch ≈ 3,363 / 895 (unchanged — accepted residual).
3. `dim_student_section_enrollments` PK still unique.
4. No non-null → non-null hash drift on the dim's `student_enrollment_key`
   (compare PR-branch vs prod for rows where prod key is non-null):

   ```sql
   select count(*) as n_nonnull_drift
   from `teamster-332318.kipptaf_marts.dim_student_section_enrollments` as prod
   inner join
     `teamster-332318.dbt_cloud_pr_<job>_<pr>_marts.dim_student_section_enrollments` as pr
     using (student_section_enrollment_key)
   where
     prod.student_enrollment_key is not null
     and pr.student_enrollment_key is not null
     and prod.student_enrollment_key != pr.student_enrollment_key
   ```

   Expected: 0.

- [ ] **Step 6: Fetch CI warnings**

After CI is green, run
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. Confirm the
only new warning is the multi-stint test (~147); triage any others per the marts
pre-merge checklist.

---

## Notes / risks

- **Hash change is one-directional.** The dim's `student_enrollment_key` only
  goes NULL→populated; the facts compute their own key independently today, so
  dropping the facts' column needs no producer/consumer hash migration.
- **No Cube/Tableau consumer** reads either grade fact, so the dropped column
  breaks nothing downstream (verified: `grep -rn` in `src/cube/` is empty).
- **The kept enr inner join** in both facts preserves row population. If a
  future PR wants to remove it, that is a deliberate row-count change requiring
  its own measurement — out of scope here.
- **Nonpositive-length sections** (#4146) are untouched; the ~47
  `fct_grades_term` rows on them may keep a NULL traversed enrollment until that
  issue lands.

```

```
