# Student Teacher Linkage (single lead) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attach the single responsible teacher (section lead for assessments,
homeroom lead for attendance) to the student-data Cube surfaces, and add
per-teacher headcount and class-roster capability.

**Architecture:** Resolve one Lead Teacher per section enrollment in
`dim_student_section_enrollments` (from `bridge_course_section_teachers`,
`role = 'Lead Teacher'`, date-overlap, deduped most-recent); derive the homeroom
teacher on `dim_student_enrollments` by referencing the section dim's `HR` rows.
Expose both on the existing enrollment Cubes via a `many_to_one` join to `staff`
(no fan-out), add a section `count_students` measure, edit the three existing
collapsed student views, and add one new `student_section_enrollments_view`
roster view.

**Tech Stack:** dbt (BigQuery), Cube semantic layer (YAML), `dbt_utils`.

## Global Constraints

- dbt CLI is always `uv run dbt ...` — never bare `dbt`. Local dev target is
  `--target dev`; `--target prod` is blocked (hand prod runs to the user).
- Dev builds that depend on GCS externals need
  `--defer --state src/dbt/kipptaf/target/prod`.
- Deduplication uses `dbt_utils.deduplicate(partition_by=..., order_by=...)` —
  never `qualify row_number() = 1` or `select distinct` for dirty data.
- Date-range joins use half-open intervals (`start <= x and x < end`); for
  range-range overlap use `a.start < b.end and b.start < a.end`.
- Marts inherit `contract: enforced: true` and `materialized: view` — every new
  column must be declared in the model's `properties/*.yml` or the contract
  build fails. Do not restate `materialized`/`contract` per model.
- Nullable FK columns get a `relationships` test (which ignores NULLs) plus a
  `foreign_key` constraint with `warn_unsupported: false`. Do NOT add
  `not_null`.
- Cube: cubes stay `public: false`; only views are public. Dim joins from a fact
  set `relationship: many_to_one`. Time dims cast to `TIMESTAMP`. `role` is a
  BigQuery reserved word — backtick in SQL, `quote: true` in YAML.
- Collapsed student views surface both the teacher `staff_key` + `teacher_role`
  groupers and the teacher name on the same view — teacher work-directory names
  are staff-directory-tier info riding the wildcard include, not student PII.
- SQL style: BigQuery dialect, trailing commas in SELECT, single quotes, 88-char
  lines, no `select *` in final mart SELECT, ST06 column ordering (plain refs
  grouped by source table, then constants, simple funcs, logicals, case,
  window).
- Trunk runs at commit (`fmt`) and pre-push (`check`). Verify SQL/YAML with
  `/workspaces/teamster/.trunk/tools/trunk check --force <files>` before
  pushing.
- Cube dev testing requires pointing `sql_table` at the dev
  `zz_<user>_kipptaf_marts` copy and running the Cube dev server (Claude cannot
  run it — hand to the user), then reverting `sql_table` before commit. Never
  commit a `zz_*` redirect.

---

### Task 1: Resolve lead teacher on `dim_student_section_enrollments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml`

**Interfaces:**

- Consumes: `bridge_course_section_teachers` (`course_section_key`, `staff_key`,
  `role`, `effective_start_date`, `effective_end_date`);
  `base_powerschool__course_enrollments.courses_credittype`.
- Produces: three new columns on `dim_student_section_enrollments` —
  `lead_teacher_staff_key` (nullable string FK to `dim_staff.staff_key`),
  `teacher_role` (string), `is_homeroom` (boolean). Grain unchanged: one row per
  `student_section_enrollment_key`.

- [ ] **Step 1: Carry `courses_credittype` through the existing CTEs**

In `dim_student_section_enrollments.sql`, add `cc.courses_credittype,` to the
`enrollment_overlap` CTE select (with the other `cc.*` columns, after
`cc.is_dropped_course,`):

```sql
            cc.is_dropped_section,
            cc.is_dropped_course,
            cc.courses_credittype,
```

Add `er.courses_credittype,` to the `course_enrollments_joined` CTE select
(after `er.is_dropped_course,`):

```sql
            er.is_dropped_section,
            er.is_dropped_course,
            er.courses_credittype,
```

- [ ] **Step 2: Wrap the existing final SELECT as a `section_enrollments` CTE
      and add teacher CTEs**

Replace the final `select ... from course_enrollments_joined` block with a CTE
named `section_enrollments` holding the exact same select (add
`courses_credittype,` to its column list), then append the teacher-resolution
CTEs and a new final SELECT:

```sql
    section_enrollments as (
        select
            cc_academic_year as academic_year,
            cc_dateenrolled as entry_date,
            cc_dateleft as exit_date,
            is_dropped_section,
            is_dropped_course,
            courses_credittype,

            {{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
            as student_section_enrollment_key,

            {{
                dbt_utils.generate_surrogate_key(
                    ["sections_dcid", "_dbt_source_project"]
                )
            }} as course_section_key,

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
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    lead_teacher_overlap as (
        select
            se.student_section_enrollment_key,

            bcst.staff_key as lead_teacher_staff_key,
            bcst.`role` as teacher_role,
            bcst.effective_start_date,
        from section_enrollments as se
        left join
            {{ ref("bridge_course_section_teachers") }} as bcst
            on se.course_section_key = bcst.course_section_key
            and bcst.`role` = 'Lead Teacher'
            and bcst.effective_start_date < coalesce(se.exit_date, cast('9999-12-31' as date))
            and se.entry_date < coalesce(bcst.effective_end_date, cast('9999-12-31' as date))
    ),

    lead_teacher_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="lead_teacher_overlap",
                partition_by="student_section_enrollment_key",
                order_by="effective_start_date desc",
            )
        }}
    )

select
    se.academic_year,
    se.entry_date,
    se.exit_date,
    se.is_dropped_section,
    se.is_dropped_course,
    se.student_section_enrollment_key,
    se.course_section_key,
    se.student_enrollment_key,
    se.term_key,

    ltr.lead_teacher_staff_key,
    ltr.teacher_role,

    -- Shipped as ('HR', 'Advisory') -- the implementation diverged from this
    -- plan's original ('HR', 'Homeroom') shorthand; both models agree with
    -- each other via var("homeroom_credit_types"), which is what matters.
    se.courses_credittype in ('HR', 'Advisory') as is_homeroom,
from section_enrollments as se
left join
    lead_teacher_resolved as ltr
    on se.student_section_enrollment_key = ltr.student_section_enrollment_key
```

- [ ] **Step 3: Declare the new columns + tests in the properties YAML**

In `properties/dim_student_section_enrollments.yml`, append to the `columns:`
list (after `is_dropped_course`). Sort `lead_teacher_staff_key` (has per-column
tests) toward the top of the column list per YAML conventions; the block below
is the content to add:

```yaml
- name: lead_teacher_staff_key
  data_type: string
  description: >-
    Staff key of the section's Lead Teacher, resolved from
    bridge_course_section_teachers by course_section_key with a date overlap of
    the teacher assignment window and the section enrollment, deduplicated to
    the most-recent lead on a mid-year handoff. FK to dim_staff. Null when the
    section has no Lead Teacher assignment overlapping the enrollment (expected
    for a minority of rows).
  constraints:
    - type: foreign_key
      to: ref('dim_staff')
      to_columns: [staff_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_staff')
          field: staff_key
- name: teacher_role
  data_type: string
  description: >-
    Role name of the resolved teacher from the section-teacher bridge. Always
    Lead Teacher in this dimension (co-teacher and other roles are not surfaced
    here). Null when no lead teacher resolved.
- name: is_homeroom
  data_type: boolean
  description: >-
    TRUE when the section's credit type is HR (homeroom / advisory). Drives the
    homeroom-teacher derivation on dim_student_enrollments.
```

- [ ] **Step 4: Build in dev and verify tests pass**

Run:

```bash
uv run dbt build --select dim_student_section_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state src/dbt/kipptaf/target/prod
```

Expected: build SUCCESS; `unique` + `not_null` on
`student_section_enrollment_key` PASS; new `relationships`
(`lead_teacher_staff_key -> dim_staff`) PASS. If the PK `unique` test FAILS, the
teacher join fanned — the dedup `partition_by` / `order_by` is wrong; fix before
proceeding.

- [ ] **Step 5: Spot-check the resolved data in BigQuery**

Run via the BigQuery MCP against the dev schema
`zz_<user>_kipptaf_marts.dim_student_section_enrollments`:

```sql
select
  countif(lead_teacher_staff_key is null) as n_null_teacher,
  count(*) as n_rows,
  round(100 * countif(lead_teacher_staff_key is null) / count(*), 1) as pct_null,
  countif(is_homeroom) as n_homeroom,
from `teamster-332318`.`zz_<user>_kipptaf_marts`.dim_student_section_enrollments
where academic_year = 2025
```

Expected: `pct_null` roughly 5–8% (the known coverage gap), `n_homeroom` > 0. A
`pct_null` near 100% means the join keys or date overlap are wrong.

- [ ] **Step 6: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_section_enrollments.yml
git commit -m "feat(dbt): add lead teacher + is_homeroom to dim_student_section_enrollments"
```

---

### Task 2: Derive homeroom teacher on `dim_student_enrollments`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml`

**Interfaces:**

- Consumes: `base_powerschool__course_enrollments` (HR-credit sections),
  `bridge_course_section_teachers` (Lead Teacher), and
  `int_powerschool__student_enrollment_union` (stints) — resolved independently,
  NOT by reffing `dim_student_section_enrollments`.
- Produces: one new column `homeroom_teacher_staff_key` (nullable string FK to
  `dim_staff.staff_key`). Grain unchanged: one row per `student_enrollment_key`.
- **Cycle avoidance:** `dim_student_section_enrollments` declares a
  `foreign_key` constraint `to: ref('dim_student_enrollments')`, and in this dbt
  version a `to: ref(...)` FK constraint DOES create a model-build DAG edge
  (section dim depends on enrollment dim). So `dim_student_enrollments` must NOT
  `ref()` the section dim — that would cycle. It resolves the homeroom teacher
  directly from `base_powerschool__course_enrollments` +
  `bridge_course_section_teachers` + the stint union instead, leaving the
  section dim's FK constraint (and its ERD edge) intact.

- [ ] **Step 1: Add homeroom-resolution CTEs and wrap the existing SELECT**

In `dim_student_enrollments.sql`, wrap the current
`select ... from ... as enr left join ...` as a CTE named `enrollments`, and
prepend the homeroom CTEs. Final file shape:

```sql
with
    homeroom_sections as (
        select
            cc.cc_studentid,
            cc.cc_yearid,
            cc.sections_schoolid,
            cc._dbt_source_project,
            cc.cc_dateenrolled,
            cc.cc_dateleft,

            {{
                dbt_utils.generate_surrogate_key(
                    ["cc.sections_dcid", "cc._dbt_source_project"]
                )
            }} as course_section_key,
        from {{ ref("base_powerschool__course_enrollments") }} as cc
        where
            -- Shipped as ('HR', 'Advisory') -- see the divergence note above.
            cc.courses_credittype in ('HR', 'Advisory')
            and not cc.is_dropped_section
            and not cc.is_dropped_course
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    homeroom_teacher as (
        select
            hs.cc_dateenrolled,

            bcst.effective_start_date,
            bcst.staff_key as homeroom_teacher_staff_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "s.student_number",
                        "s._dbt_source_project",
                        "s.academic_year",
                        "s.entrydate",
                    ]
                )
            }} as student_enrollment_key,
        from homeroom_sections as hs
        inner join
            {{ ref("int_powerschool__student_enrollment_union") }} as s
            on hs.cc_studentid = s.studentid
            and hs.sections_schoolid = s.schoolid
            and hs.cc_yearid = s.yearid
            and hs._dbt_source_project = s._dbt_source_project
            and hs.cc_dateenrolled >= s.entrydate
            and hs.cc_dateenrolled < s.exitdate
        left join
            {{ ref("bridge_course_section_teachers") }} as bcst
            on hs.course_section_key = bcst.course_section_key
            and bcst.`role` = 'Lead Teacher'
            and bcst.effective_start_date
            < coalesce(hs.cc_dateleft, cast('9999-12-31' as date))
            and hs.cc_dateenrolled
            < coalesce(bcst.effective_end_date, cast('9999-12-31' as date))
    ),

    homeroom_resolved as (
        {{
            dbt_utils.deduplicate(
                relation="homeroom_teacher",
                partition_by="student_enrollment_key",
                order_by="cc_dateenrolled desc, effective_start_date desc",
            )
        }}
    ),

    enrollments as (
        select
            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "enr.student_number",
                        "enr._dbt_source_project",
                        "enr.academic_year",
                        "enr.entrydate",
                    ]
                )
            }} as student_enrollment_key,

            {{ dbt_utils.generate_surrogate_key(["enr.student_number"]) }}
            as student_key,

            sch.location_key,

            enr.entrydate as entry_date_key,
            enr.exitdate as exit_date_key,

            enr.academic_year,
            enr.grade_level,
            enr.cohort_primary as graduation_year,
            enr.is_retained_year,
            enr.year_in_network,
        from {{ ref("int_powerschool__student_enrollment_union") }} as enr
        left join
            {{ ref("stg_powerschool__schools") }} as sch
            on enr.schoolid = sch.school_number
            and enr._dbt_source_project = sch._dbt_source_project
    )

select
    e.student_enrollment_key,
    e.student_key,
    e.location_key,
    e.entry_date_key,
    e.exit_date_key,
    e.academic_year,
    e.grade_level,
    e.graduation_year,
    e.is_retained_year,
    e.year_in_network,

    hr.homeroom_teacher_staff_key,
from enrollments as e
left join
    homeroom_resolved as hr
    on e.student_enrollment_key = hr.student_enrollment_key
```

- [ ] **Step 2: Declare the new column + test in the properties YAML**

In `properties/dim_student_enrollments.yml`, append to `columns:` (place it
after `student_key` so the per-column-tested FK sits near the top per
conventions):

```yaml
- name: homeroom_teacher_staff_key
  data_type: string
  description: >-
    Staff key of the student's homeroom/advisory Lead Teacher for this
    enrollment stint — the Lead Teacher of the stint's HR-credit section (from
    dim_student_section_enrollments, is_homeroom rows), deduplicated to the
    most-recent on a mid-year homeroom change. FK to dim_staff. Null when the
    stint has no resolvable HR section lead.
  constraints:
    - type: foreign_key
      to: ref('dim_staff')
      to_columns: [staff_key]
      warn_unsupported: false
  data_tests:
    - relationships:
        arguments:
          to: ref('dim_staff')
          field: staff_key
```

- [ ] **Step 3: Build both dims in dev and verify tests pass**

Run (build the section dim first so the ref resolves in dev):

```bash
uv run dbt build \
  --select dim_student_section_enrollments dim_student_enrollments \
  --project-dir src/dbt/kipptaf --target dev \
  --defer --state src/dbt/kipptaf/target/prod
```

Expected: both build SUCCESS; `unique`/`not_null` on
`dim_student_enrollments.student_enrollment_key` PASS; new `relationships`
(`homeroom_teacher_staff_key -> dim_staff`) PASS.

- [ ] **Step 4: Spot-check homeroom coverage in BigQuery**

```sql
select
  countif(homeroom_teacher_staff_key is null) as n_null,
  count(*) as n_rows,
  round(100 * countif(homeroom_teacher_staff_key is null) / count(*), 1) as pct_null,
from `teamster-332318`.`zz_<user>_kipptaf_marts`.dim_student_enrollments
where academic_year = 2025
```

Expected: `pct_null` roughly 4–6% (homeroom coverage gap). Near 100% means the
`is_homeroom` filter or the join is wrong.

- [ ] **Step 5: Commit**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_student_enrollments.yml
git commit -m "feat(dbt): derive homeroom_teacher_staff_key on dim_student_enrollments"
```

---

### Task 3: Widen the `student_section_enrollments` cube (dims, staff join, count_students)

**Files:**

- Modify: `src/cube/model/cubes/students/student_section_enrollments.yml`

**Interfaces:**

- Consumes: Task 1 columns (`lead_teacher_staff_key`, `teacher_role`,
  `is_homeroom`).
- Produces: cube dims `lead_teacher_staff_key`, `teacher_role`, `is_homeroom`; a
  `many_to_one` join `staff` on `lead_teacher_staff_key`; a `count_students`
  measure (`count_distinct` on the student). These become the join anchors the
  assessment views and the new roster views consume.

- [ ] **Step 1: Add the `staff` join**

In `student_section_enrollments.yml`, add to the `joins:` list:

```yaml
# Lead teacher name/attributes. many_to_one — one lead per enrollment
# after dbt resolution — so no fan-out.
- name: staff
  sql: "{staff.staff_key} = {CUBE}.lead_teacher_staff_key"
  relationship: many_to_one
```

- [ ] **Step 2: Add the teacher dimensions**

Add to the `dimensions:` list (after `is_dropped_course`):

```yaml
# Degenerate FK to staff — teacher name comes via the staff join.
- name: lead_teacher_staff_key
  description: FK to staff — the section's Lead Teacher.
  sql: lead_teacher_staff_key
  type: string

- name: teacher_role
  description: Role of the resolved teacher (always Lead Teacher here).
  sql: teacher_role
  type: string
  public: true

- name: is_homeroom
  description: TRUE when this is an HR-credit (homeroom/advisory) section.
  sql: is_homeroom
  type: boolean
  public: true
```

- [ ] **Step 3: Add the `count_students` measure**

Append a `measures:` block to the cube:

```yaml
measures:
  - name: count_students
    description: >-
      Distinct students with a section enrollment in the filtered slice. Answers
      "how many students does this teacher teach?" when grouped by the lead
      teacher. count_distinct on the student, so it is fan-safe.
    sql: "{students.student_key}"
    type: count_distinct
    public: true
```

- [ ] **Step 4: Compile-test against the dev schema (user-run)**

Claude cannot run the Cube dev server. Hand to the user: temporarily set
`sql_table: zz_<user>_kipptaf_marts.dim_student_section_enrollments` on this
cube, start the **Cube: Dev Server** VS Code task, and confirm a `/sql` compile
of `student_section_enrollments.count_students` grouped by
`student_section_enrollments.lead_teacher_staff_key` succeeds. If
`{students.student_key}` fails to resolve, fall back to
`sql: "{student_school_enrollments.student_key}"`. Revert `sql_table` to
`kipptaf_marts.dim_student_section_enrollments` before committing.

- [ ] **Step 5: Verify lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/cubes/students/student_section_enrollments.yml
git add src/cube/model/cubes/students/student_section_enrollments.yml
git commit -m "feat(cube): add lead teacher dims, staff join, and count_students to student_section_enrollments"
```

---

### Task 4: Widen the `student_school_enrollments` cube (homeroom dim + staff join)

**Files:**

- Modify: `src/cube/model/cubes/students/student_school_enrollments.yml`

**Interfaces:**

- Consumes: Task 2 column `homeroom_teacher_staff_key`.
- Produces: cube dim `homeroom_teacher_staff_key`; `many_to_one` join `staff` on
  it. Anchors the homeroom teacher for the attendance and enrollment views.

- [ ] **Step 1: Add the `staff` join**

Add to the `joins:` list in `student_school_enrollments.yml`:

```yaml
# Homeroom teacher name/attributes. many_to_one — one homeroom lead per
# enrollment after dbt resolution — so no fan-out.
- name: staff
  sql: "{staff.staff_key} = {CUBE}.homeroom_teacher_staff_key"
  relationship: many_to_one
```

- [ ] **Step 2: Add the homeroom teacher dimension**

Add to the `dimensions:` list:

```yaml
# Degenerate FK to staff — homeroom teacher name comes via the staff join.
- name: homeroom_teacher_staff_key
  description: FK to staff — the student's homeroom/advisory Lead Teacher.
  sql: homeroom_teacher_staff_key
  type: string
```

- [ ] **Step 3: Compile-test against dev (user-run) and revert**

Same procedure as Task 3 Step 4, redirecting this cube's `sql_table` to
`zz_<user>_kipptaf_marts.dim_student_enrollments`; confirm the `staff` join
compiles; revert `sql_table` before commit.

- [ ] **Step 4: Verify lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/cubes/students/student_school_enrollments.yml
git add src/cube/model/cubes/students/student_school_enrollments.yml
git commit -m "feat(cube): add homeroom teacher dim and staff join to student_school_enrollments"
```

---

### Task 5: Add the section teacher to the assessment view

**Files:**

- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`

**Interfaces:**

- Consumes: Task 3 (`lead_teacher_staff_key`, `teacher_role` on
  `student_section_enrollments`; `staff` join).
- Produces: a `Teacher` folder on the collapsed view.

- [ ] **Step 1: Add the teacher members**

In `student_assessment_scores_view.yml`, add `lead_teacher_staff_key` and
`teacher_role` to the existing
`join_path: student_assessment_scores.student_section_enrollments` includes
block, and add a new join_path for the teacher name (the cube join alias is
`staff_lead_teacher`):

```yaml
- join_path: student_assessment_scores.student_section_enrollments.staff_lead_teacher
  prefix: true
  includes:
    - full_name
    - first_name
    - last_name
```

Add a `Teacher` folder under `meta.folders` (the `prefix: true` join surfaces
the name members as `staff_lead_teacher_*`):

```yaml
- name: Teacher
  members:
    - lead_teacher_staff_key
    - teacher_role
    - staff_lead_teacher_full_name
    - staff_lead_teacher_first_name
    - staff_lead_teacher_last_name
```

- [ ] **Step 2: Leave the access_policy unchanged**

The collapsed view already gates access through its three `student-*` groups
(`student-region` / `student-school` / `student-network`), each with
`member_level: { includes: "*" }` and, for region/school, a `row_level` location
filter (bare `region_key` / `abbreviation` — this view joins `locations`
unprefixed). Teacher name/`staff_key`/`teacher_role` members ride the wildcard
include as staff-directory-tier info, so no PII excludes and no new group are
needed. Leave `access_policy` unchanged.

- [ ] **Step 3: Compile-test (user-run), lint, commit**

Have the user confirm the view compiles in the Cube dev server (with the Task 1
dev `sql_table` redirect active), then:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/views/student_assessments/student_assessment_scores_view.yml
git add src/cube/model/views/student_assessments/student_assessment_scores_view.yml
git commit -m "feat(cube): surface section lead teacher on assessment scores view"
```

---

### Task 6: Add the homeroom teacher to the attendance view

**Files:**

- Modify: `src/cube/model/views/student_attendance/student_attendance_view.yml`

**Interfaces:**

- Consumes: Task 4 (`homeroom_teacher_staff_key` + `staff` join on
  `student_school_enrollments`).
- Produces: a `Teacher` folder on the collapsed view.

- [ ] **Step 1: Add the teacher members**

In `student_attendance_view.yml`, add `homeroom_teacher_staff_key` to the
existing `join_path: student_attendance.student_school_enrollments` includes
block, and add the teacher-name join_path (the cube join alias is
`staff_homeroom_teacher`):

```yaml
- join_path: student_attendance.student_school_enrollments.staff_homeroom_teacher
  prefix: true
  includes:
    - full_name
    - first_name
    - last_name
```

Add a `Teacher` folder under `meta.folders` (the `prefix: true` join surfaces
the name members as `staff_homeroom_teacher_*`):

```yaml
- name: Teacher
  members:
    - homeroom_teacher_staff_key
    - staff_homeroom_teacher_full_name
    - staff_homeroom_teacher_first_name
    - staff_homeroom_teacher_last_name
```

- [ ] **Step 2: Leave the access_policy unchanged**

The collapsed view gates access through its three `student-*` groups, each with
`member_level: { includes: "*" }` and, for region/school, a `row_level` location
filter (prefixed `locations_region_key` / `locations_abbreviation`). Teacher
name and `homeroom_teacher_staff_key` members ride the wildcard include as
staff-directory-tier info, so no PII excludes and no new group are needed. Leave
`access_policy` unchanged.

- [ ] **Step 3: Compile-test (user-run), lint, commit**

Have the user confirm the view compiles (Task 2 dev `sql_table` redirect
active), then:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/views/student_attendance/student_attendance_view.yml
git add src/cube/model/views/student_attendance/student_attendance_view.yml
git commit -m "feat(cube): surface homeroom teacher on attendance view"
```

---

### Task 7: Add the homeroom teacher to the enrollment view

**Files:**

- Modify: `src/cube/model/views/students/student_enrollments_view.yml`

**Interfaces:**

- Consumes: Task 4 (`homeroom_teacher_staff_key` + `staff` join).
- Produces: a `Teacher` folder; with the existing `count_students`, this answers
  homeroom headcount and the advisory roster from the one collapsed view.

- [ ] **Step 1: Add the teacher members**

In `student_enrollments_view.yml`, add `homeroom_teacher_staff_key` to the
`join_path: student_enrollments.student_school_enrollments` (prefix: false)
includes block, and add the teacher-name join_path (the cube join alias is
`staff_homeroom_teacher`):

```yaml
- join_path: student_enrollments.student_school_enrollments.staff_homeroom_teacher
  prefix: true
  includes:
    - full_name
    - first_name
    - last_name
```

Add the folder (the `prefix: true` join surfaces the name members as
`staff_homeroom_teacher_*`):

```yaml
- name: Teacher
  members:
    - homeroom_teacher_staff_key
    - staff_homeroom_teacher_full_name
    - staff_homeroom_teacher_first_name
    - staff_homeroom_teacher_last_name
```

- [ ] **Step 2: Leave the access_policy unchanged**

The collapsed view gates access through its three `student-*` groups, each with
`member_level: { includes: "*" }` and, for region/school, a `row_level` location
filter (prefixed `locations_region_key` / `locations_abbreviation`). Teacher
members ride the wildcard include as staff-directory-tier info — no PII
excludes, no new group. Leave `access_policy` unchanged.

- [ ] **Step 3: Compile-test (user-run), lint, commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/views/students/student_enrollments_view.yml
git add src/cube/model/views/students/student_enrollments_view.yml
git commit -m "feat(cube): surface homeroom teacher on enrollment view"
```

---

### Task 8: Create the `student_section_enrollments_view` roster view

**Files:**

- Create: `src/cube/model/views/students/student_section_enrollments_view.yml`

**Interfaces:**

- Consumes: Task 3 cube (`count_students`, teacher dims, `staff` join) and its
  existing joins (`course_sections`, `terms`, `student_school_enrollments` →
  `students` / `locations` / `student_enrollment_status`).
- Produces: one new collapsed public view — a per-teacher class roster and a
  section/teacher headcount surface on the same view (row-level identifiers plus
  aggregate breakdowns).

- [ ] **Step 1: Create the collapsed roster view**

Write `student_section_enrollments_view.yml` (the cube join alias for the lead
teacher is `staff_lead_teacher`, so its `prefix: true` name members surface as
`staff_lead_teacher_*`; `locations` is joined `prefix: true`, so its filter
members are `locations_region_key` / `locations_abbreviation`):

```yaml
views:
  - name: student_section_enrollments_view
    description: >-
      Student section enrollments — row-level (one row per student x section
      enrollment) and aggregate headcounts in a single view. Use for per-teacher
      class rosters (filter to a lead teacher) and section drill-down.
      count_students is a distinct-student headcount, correct per teacher —
      grouped by lead teacher it answers "how many students does this teacher
      teach?". Contains direct student identifiers — see access_policy for PII
      gating.

    cubes:
      - join_path: student_section_enrollments
        includes:
          - count_students
          - student_section_enrollment_key
          - student_enrollment_key
          - academic_year
          - entry_date
          - exit_date
          - is_dropped_section
          - is_dropped_course
          - is_homeroom
          - teacher_role
          - lead_teacher_staff_key

      - join_path: student_section_enrollments.staff_lead_teacher
        prefix: true
        includes:
          - full_name
          - first_name
          - last_name

      - join_path: student_section_enrollments.course_sections.courses
        includes:
          - discipline
          - course_title
          - course_code
          - credit_type
          - is_foundations

      - join_path: student_section_enrollments.course_sections
        includes:
          - identifier
          - period

      - join_path: student_section_enrollments.terms
        includes:
          - semester
          - term_name
          - term_code
          - term_type

      - join_path: student_section_enrollments.student_school_enrollments
        prefix: false
        includes:
          - grade_level
          - graduation_year
          - year_in_network
          - is_retained_year

      - join_path: student_section_enrollments.student_school_enrollments.students
        prefix: false
        includes:
          - student_key
          - full_name
          - birth_date
          - lea_student_identifier
          - state_student_identifier
          - gender_identity
          - race
          - enrollment_status
          - is_gifted

      - join_path: student_section_enrollments.student_school_enrollments.locations
        prefix: true
        includes:
          - location_name
          - abbreviation
          - region_key
          - grade_band
          - campus
          - city

      - join_path: student_section_enrollments.student_school_enrollments.locations.regions
        prefix: true
        includes:
          - region_name
          - state

    meta:
      folders:
        - name: Teacher
          members:
            - lead_teacher_staff_key
            - teacher_role
            - staff_lead_teacher_full_name
            - staff_lead_teacher_first_name
            - staff_lead_teacher_last_name
        - name: Course
          members:
            - discipline
            - course_title
            - course_code
            - credit_type
            - is_foundations
            - identifier
            - period
        - name: Term
          members:
            - semester
            - term_name
            - term_code
            - term_type
        - name: Location
          members:
            - locations_location_name
            - locations_abbreviation
            - locations_region_key
            - locations_grade_band
            - locations_campus
            - locations_city
            - regions_region_name
            - regions_state
        - name: Student
          members:
            - student_key
            - full_name
            - birth_date
            - lea_student_identifier
            - state_student_identifier
            - gender_identity
            - race
            - enrollment_status
            - is_gifted
        - name: Enrollment
          members:
            - student_section_enrollment_key
            - student_enrollment_key
            - academic_year
            - entry_date
            - exit_date
            - is_homeroom
            - is_dropped_section
            - is_dropped_course
            - grade_level
            - graduation_year
            - year_in_network
            - is_retained_year

    access_policy:
      # Row-level location scoping. A viewer holds exactly one student-<scope>
      # group; none => no group => default-deny. Teacher fields
      # (staff_lead_teacher_* names, lead_teacher_staff_key) ride the wildcard
      # include — staff-directory-tier info, not student PII.
      - group: student-region
        member_level:
          includes: "*"
        row_level:
          filters:
            - member: locations_region_key
              operator: equals
              values: ["{ securityContext.region_key }"]
      - group: student-school
        member_level:
          includes: "*"
        row_level:
          filters:
            - member: locations_abbreviation
              operator: equals
              values: ["{ securityContext.location_abbreviation }"]
      - group: student-network
        member_level:
          includes: "*"
        # network: no row_level (sees all locations)
```

- [ ] **Step 2: Compile-test (user-run)**

Have the user confirm the new view compiles and `/load` returns a class roster
when filtered to a `lead_teacher_staff_key` (Task 1 dev `sql_table` redirect
active). Watch for a diamond-path error reaching `locations` — the section cube
reaches `locations` only through `student_school_enrollments`; if Cube reports a
diamond, remove any redundant `locations` join_path.

- [ ] **Step 3: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force \
  src/cube/model/views/students/student_section_enrollments_view.yml
git add src/cube/model/views/students/student_section_enrollments_view.yml
git commit -m "feat(cube): add student_section_enrollments_view roster view"
```

---

### Task 9: End-to-end measure-safety verification

**Files:** none (verification only).

**Interfaces:** Consumes all prior tasks.

- [ ] **Step 1: Confirm no fan-out on the fact measures**

Via the Cube MCP (or dev server), for the same filter (single academic year,
single school), confirm each measure is identical grouped-by-teacher vs.
ungrouped:

- `student_attendance_view.count_students` and `avg_daily_attendance` grouped by
  `homeroom_teacher_staff_key` vs. ungrouped.
- `student_assessment_scores_view.count_scores` grouped by
  `lead_teacher_staff_key` vs. ungrouped.
- One snapshot measure
  (`student_attendance_view.count_chronically_absent_year_end`) grouped by
  teacher vs. ungrouped.

Expected: totals match (the join is `many_to_one`, so no fan). Any divergence
means a resolution is not 1:1 — return to Task 1/2 and check the PK `unique`
test.

- [ ] **Step 2: Confirm the headcount + roster answer the question**

Via the Cube MCP: `student_section_enrollments_view.count_students` grouped by
`lead_teacher_staff_key` returns per-teacher counts; a
`student_section_enrollments_view` query filtered to one
`lead_teacher_staff_key` returns that teacher's student list.

- [ ] **Step 3: Confirm access gating**

Confirm the new roster view (teacher blocks included) is default-denied for a
security context holding none of the three `student-*` groups, and that a
`student-region` / `student-school` viewer sees only their in-scope locations
via the `row_level` filter — a `student-network` viewer sees every location. All
three groups see every field (`member_level: { includes: "*" }`), so there is no
separate PII tier to test.

- [ ] **Step 4: Final lint sweep and push**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force src/cube/model/ src/dbt/kipptaf/models/marts/dimensions/
```

Confirm all `sql_table` redirects are reverted to `kipptaf_marts.*` (grep for
`zz_`), then push the branch. dbt Cloud CI (`state:modified+`) will build the
two modified dims and their tests.

---

## Notes for the implementer

- **Cube can't be compiled by Claude.** Every "compile-test (user-run)" step
  needs the user to run the Cube dev server (VS Code task **Cube: Dev Server**)
  with the dim `sql_table` temporarily redirected to the dev
  `zz_<user>_kipptaf_marts` copy, then revert before commit. Never commit a
  `zz_*` redirect (name files explicitly in `git add`).
- **Deferred (not this plan):** the co-taught / multi-lead many-to-many teacher
  breakdown (issue #4289) and the manager / reporting-chain linkage (blocked on
  #4269). Do not add a fanning teacher join to any view here.
