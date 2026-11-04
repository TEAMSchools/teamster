# Academic Goals Dashboard View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the goal-recomputing Tableau view with a joins-only reporting
view fed by stored bucket uploads (PowerSchool, Focus) and the goals sheet.

**Architecture:** One new domain intermediate decodes bucket assignments from
both stores into a single student x year x subject model; the existing subjects
roster is rewired to read it (replacing its inline PowerSchool-only decode); a
second new intermediate relocates the benchmark-score panel out of the rpt
layer; the new rpt joins roster x benchmarks x goals with no arithmetic.

**Tech Stack:** dbt (BigQuery), dbt unit tests, Tableau (repoint happens outside
this repo).

**Spec:**
`docs/superpowers/specs/2026-10-14-academic-goals-dashboard-view-design.md`
(read it first; Task 1 adds a revision section it depends on).

## Global Constraints

- Work only through the worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-goals-dashboard-view`,
  branch `anthonygwalters/feat/claude-goals-dashboard-view`, issue #5890.
- Never run bare `python`/`dbt` — always `uv run`, with
  `--project-dir <worktree>/src/dbt/kipptaf`.
- Invoke the `dbt-local-dev` skill before the first local dbt command; it owns
  target/defer flags and stale-dev traps. Invoke `trunk-lint` before the first
  trunk run.
- SQL follows `.claude/rules/dbt-sql.md` (auto-loads): no `qualify`, named
  `group by`, trailing commas, `dbt_utils.deduplicate` for row picks.
- Do not re-create the two baselined A1 edges (`stg_renlearn__star`,
  `base_powerschool__course_enrollments`) on any NEW model; they are legal only
  inside existing `int_` models.
- Never join two unioned regional models on `_dbt_source_relation`; use
  `_dbt_source_project` (A10).
- New-model scope is `academic_year >= 2026` in the rpt only; intermediates
  carry all years they observe.
- No PII in commits, PR text, or issue comments: no student names or numbers in
  any verification output you paste.
- Commit after every green step; messages are conventional commits ending with
  the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

## Review Focus

1. A student uploaded to two bucket programs for one subject (amendment
   mistake): the view must pick the latest assignment and flag, not duplicate
   the student. Pinned by the Task 3 unit test (`re-assignment picks latest`)
   and the `n_active_assignments` warn test.
2. The same `student_number` in two regions (numbers repeat across PowerSchool
   instances): rows must not cross regions. Pinned by region in the Task 3 grain
   test and the roster join's region key (Task 4).
3. An enrolled student with no stored assignment (mid-year arrival): must appear
   as Bucket 4 with goals populated, not drop out. Pinned by the Task 6 unit
   test (`defaults` case) and Task 4's NJ tier-parity query.
4. A Miami kindergartner with both a Star BOY and an i-Ready row: must produce
   one benchmark row, Star first. Pinned by the Task 5 unit test
   (`miami k prefers star boy`).
5. A school x grade x subject with no goals-sheet row: the student row must
   survive with null goal columns (visible gap, not a dropped student). Pinned
   by the Task 6 unit test (`missing goal row keeps student`).

---

### Task 1: Spec revision section

**Files:**

- Modify:
  `docs/superpowers/specs/2026-10-14-academic-goals-dashboard-view-design.md`

**Interfaces:**

- Produces: the design record later tasks implement; no code.

- [ ] **Step 1: Append the revision section**

Add at the end of the spec file:

```markdown
## Revision 2026-10-14 (pre-implementation)

Plan-time code reading changed three things:

1. `int_extracts__student_enrollments_subjects` already decodes PowerSchool
   bucket programs inline (`bucket_programs`/`bucket_dedupe` CTEs ->
   `nj_student_tier`, Bucket 4 default) with ~15 downstream consumers, including
   `rpt_illuminate__programs` (the feed that populates Illuminate Student
   Programs) and `rpt_tableau__ddi_dashboard`. Per A4 ("extend instead of adding
   a sibling") and the reuse-identity rule in `src/dbt/kipptaf/CLAUDE.md`,
   `int_students__bucket_assignments` becomes the ONE home for the decode and
   the subjects roster is rewired to read it. Side effect, intended: Miami rows
   of `nj_student_tier` change from a constant Bucket 4 (PowerSchool has no
   Miami) to real Focus-stored tiers, across all consumers. NJ values are
   unchanged (same decode, same latest-assignment pick).
2. Grain carries region: student numbers repeat across PowerSchool instances, so
   the bucket model's key is academic_year x region x student_number x subject,
   and every join to it includes region.
3. The double-upload gate is a latest-assignment-wins pick (matching current
   roster behavior) plus an `n_active_assignments <= 1` warn test, not an
   error-severity uniqueness failure: amendment history legitimately leaves
   exited rows behind, and a hard error would fire on every re-assignment.
4. Known display limitation: the Miami K benchmark panel reads the standard Star
   export (`stg_renlearn__star`) while the generator reads the FAST Star file;
   the panel switches when teamster#5377 stages that file.
5. Focus ids need no crosswalk: the Focus `student_id` (8400-prefixed) IS the
   Miami student number (see `int_focus__students`).
```

- [ ] **Step 2: Lint and commit**

```bash
w=/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-goals-dashboard-view
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/specs/2026-10-14-academic-goals-dashboard-view-design.md </dev/null
git -C "$w" add docs/superpowers/specs/ && git -C "$w" commit -m "docs(goals-dashboard): record plan-time design revisions"
```

---

### Task 2: Focus custom-group sources and wrappers

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create: `src/dbt/kipptaf/models/focus/staging/stg_focus__student_groups.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__students_join_groups.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__student_groups.yml`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__students_join_groups.yml`

**Interfaces:**

- Consumes: kippmiami relations `stg_focus__student_groups` (columns `id`,
  `title`, `assignment_type`, `start_date`, `end_date`, ...) and
  `stg_focus__students_join_groups` (columns `id`, `group_id`, `student_id`,
  `syear`, ...), both built by the focus package in kippmiami.
- Produces: kipptaf refs `stg_focus__student_groups` and
  `stg_focus__students_join_groups`, each `select *` plus `_dbt_source_project`.
  Task 3 reads both.

- [ ] **Step 1: Add the two source tables**

In `sources-kippmiami.yml`, under `tables:`, insert (mirroring the
`stg_focus__students` entry exactly):

```yaml
- name: stg_focus__student_groups
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - stg_focus__student_groups
- name: stg_focus__students_join_groups
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - stg_focus__students_join_groups
```

- [ ] **Step 2: Write the two wrapper models**

`stg_focus__student_groups.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "stg_focus__student_groups")
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

`stg_focus__students_join_groups.sql`: identical with
`"stg_focus__students_join_groups"` as the source table.

- [ ] **Step 3: Write the properties files**

`properties/stg_focus__student_groups.yml`:

```yaml
models:
  - name: stg_focus__student_groups
    description: >-
      Kipptaf-level union_relations passthrough of kippmiami's
      stg_focus__student_groups (Focus custom student groups, where Miami bucket
      assignments are stored). Column docs/tests live on the kippmiami source
      model.
    columns:
      - name: _dbt_source_project
        description: District code location derived from _dbt_source_relation.
```

`properties/stg_focus__students_join_groups.yml`: same shape, description
"...stg_focus__students_join_groups (student-to-custom-group memberships;
`student_id` is the Miami student number)...".

Per `.claude/rules/dbt-models.md`, kipptaf `stg_` union views get **no**
uniqueness test and **no** contract.

- [ ] **Step 4: Compile against staging and verify columns**

```bash
w=/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-goals-dashboard-view
uv run dbt compile --select stg_focus__student_groups stg_focus__students_join_groups \
  --target staging --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 10
```

Read the compiled SQL under
`$w/src/dbt/kipptaf/target/compiled/.../stg_focus__student_groups.sql` and
confirm the column list expanded (an empty expansion means the `zz_stg_` copy is
missing — see `dbt-local-dev`). Expected: `id`, `title`, `assignment_type`
appear for groups; `group_id`, `student_id`, `syear` for join-groups.

- [ ] **Step 5: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/models/focus/
git -C "$w" commit -m "feat(dbt): expose Focus custom student groups to kipptaf"
```

---

### Task 3: `int_students__bucket_assignments`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__bucket_assignments.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__bucket_assignments.yml`

**Interfaces:**

- Consumes: `int_powerschool__spenrollments` (`studentid`, `academic_year`,
  `specprog_name`, `enter_date`, `exit_date`, `_dbt_source_relation`,
  `_dbt_source_project`), `int_extracts__student_enrollments` (`studentid`,
  `student_number`, `academic_year`, `rn_year`, `_dbt_source_project`), Task 2's
  two Focus wrappers.
- Produces: ref `int_students__bucket_assignments` with columns
  `academic_year int64`, `region string` (Newark/Camden/Paterson/Miami),
  `student_number int64`, `subject string` (Reading/Math), `bucket string`
  (Bucket 1/2/3), `bucket_store string` (powerschool/focus),
  `assignment_date date`, `n_active_assignments int64`. Grain: one row per
  academic_year x region x student_number x subject. Tasks 4 and the spec's
  reconciliation read it.

- [ ] **Step 1: Write the failing unit test**

In the properties yml (created fully in Step 3), the `unit_tests:` block below
is the test. Write the yml first with the model file still absent, then run Step
2 to see the expected parse failure.

- [ ] **Step 2: Run to verify it fails**

```bash
w=/workspaces/teamster/.claude/worktrees/anthonygwalters/feat/claude-goals-dashboard-view
uv run dbt parse --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 5
```

Expected: FAIL — the yml names a model node that does not exist yet.

- [ ] **Step 3: Write the model**

`int_students__bucket_assignments.sql`:

```sql
with
    powerschool_programs as (
        select
            sp.academic_year,
            sp.enter_date as assignment_date,
            sp.exit_date,

            co.student_number,

            'powerschool' as bucket_store,

            trim(split(sp.specprog_name, '-')[offset(0)]) as bucket,

            initcap(
                regexp_extract(sp._dbt_source_relation, r'kipp(\w+)_')
            ) as region,

            if(
                trim(split(sp.specprog_name, '-')[offset(1)]) = 'ELA',
                'Reading',
                'Math'
            ) as `subject`,
        from {{ ref("int_powerschool__spenrollments") }} as sp
        inner join
            {{ ref("int_extracts__student_enrollments") }} as co
            on sp.studentid = co.studentid
            and sp.academic_year = co.academic_year
            and sp._dbt_source_project = co._dbt_source_project
        where sp.specprog_name like 'Bucket%' and co.rn_year = 1
    ),

    focus_memberships as (
        select
            jg.syear as academic_year,
            jg.student_id as student_number,

            sg.end_date as exit_date,

            'Miami' as region,
            'focus' as bucket_store,

            cast(jg.created_at as date) as assignment_date,

            trim(split(sg.title, '-')[offset(0)]) as bucket,

            if(
                trim(split(sg.title, '-')[offset(1)]) = 'ELA',
                'Reading',
                'Math'
            ) as `subject`,
        from {{ ref("stg_focus__students_join_groups") }} as jg
        inner join
            {{ ref("stg_focus__student_groups") }} as sg
            on jg.group_id = sg.id
            and jg._dbt_source_project = sg._dbt_source_project
        where sg.title like 'Bucket%'
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    assignments as (
        select
            academic_year,
            region,
            student_number,
            `subject`,
            bucket,
            bucket_store,
            assignment_date,

            countif(exit_date is null) over (
                partition by academic_year, region, student_number, `subject`
            ) as n_active_assignments,
        from (
            select
                academic_year,
                region,
                student_number,
                `subject`,
                bucket,
                bucket_store,
                assignment_date,
                exit_date,
            from powerschool_programs

            union all

            select
                academic_year,
                region,
                student_number,
                `subject`,
                bucket,
                bucket_store,
                assignment_date,
                exit_date,
            from focus_memberships
        )
    )

{{
    dbt_utils.deduplicate(
        relation="assignments",
        partition_by="academic_year, region, student_number, subject",
        order_by="assignment_date desc",
    )
}}
```

Note: sqlfluff ST05 forbids the inline subquery in `from` — if lint flags it,
hoist the union into its own CTE named `assignment_union` and have `assignments`
select from it. Keep the window function in `assignments`, after the union, so
the active count sees both stores.

- [ ] **Step 4: Write the properties yml**

`properties/int_students__bucket_assignments.yml`:

```yaml
models:
  - name: int_students__bucket_assignments
    description: >-
      The single home for stored student bucket assignments: PowerSchool special
      programs (NJ) and Focus custom student groups (Miami), decoded from the
      program/group name ("Bucket 1 - ELA"). One row per academic_year x region
      x student_number x subject; where a student has assignment history
      (rollout-PD amendments exit and re-enter), the latest assignment_date
      wins. Bucket 4 is never stored - consumers coalesce a missing row to
      Bucket 4. Region is part of the grain because student numbers repeat
      across PowerSchool instances.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - academic_year
            - region
            - student_number
            - subject
    columns:
      - name: academic_year
        description: Academic year of the assignment (Focus syear as-is).
      - name: region
        description: Newark, Camden, Paterson, or Miami.
      - name: student_number
        description: Network student number (Focus student_id for Miami).
      - name: subject
        description: Reading or Math, decoded from the program/group name.
        data_tests:
          - accepted_values:
              values: ["Reading", "Math"]
      - name: bucket
        description: Stored bucket label.
        data_tests:
          - accepted_values:
              values: ["Bucket 1", "Bucket 2", "Bucket 3"]
      - name: bucket_store
        description: Which system holds the assignment.
      - name: assignment_date
        description:
          Program enter date (PS) or group-membership created date (Focus).
      - name: n_active_assignments
        description: >-
          Count of never-exited assignments sharing this grain; more than 1
          means a double upload that the latest-wins pick is masking.
        data_tests:
          - dbt_utils.expression_is_true:
              expression: "<= 1"
              config:
                severity: warn
    unit_tests:
      - name: unit_int_students__bucket_assignments
        description: >-
          Decodes both stores, picks the latest assignment on re-assignment,
          excludes non-bucket programs, and keeps same-number students in
          different regions apart.
        model: int_students__bucket_assignments
        given:
          - input: ref("int_powerschool__spenrollments")
            rows:
              - {
                  studentid: 11,
                  academic_year: 2026,
                  specprog_name: "Bucket 2 - Math",
                  enter_date: 2026-09-01,
                  exit_date: 2026-10-01,
                  _dbt_source_relation: "`t`.`kippnewark_powerschool`.`x`",
                  _dbt_source_project: "kippnewark",
                }
              - {
                  studentid: 11,
                  academic_year: 2026,
                  specprog_name: "Bucket 3 - Math",
                  enter_date: 2026-10-02,
                  exit_date: null,
                  _dbt_source_relation: "`t`.`kippnewark_powerschool`.`x`",
                  _dbt_source_project: "kippnewark",
                }
              - {
                  studentid: 12,
                  academic_year: 2026,
                  specprog_name: "MTSS Math",
                  enter_date: 2026-09-01,
                  exit_date: null,
                  _dbt_source_relation: "`t`.`kippnewark_powerschool`.`x`",
                  _dbt_source_project: "kippnewark",
                }
              - {
                  studentid: 13,
                  academic_year: 2026,
                  specprog_name: "Bucket 1 - ELA",
                  enter_date: 2026-09-01,
                  exit_date: null,
                  _dbt_source_relation: "`t`.`kippcamden_powerschool`.`x`",
                  _dbt_source_project: "kippcamden",
                }
          - input: ref("int_extracts__student_enrollments")
            rows:
              - {
                  studentid: 11,
                  student_number: 5001,
                  academic_year: 2026,
                  rn_year: 1,
                  _dbt_source_project: "kippnewark",
                }
              - {
                  studentid: 12,
                  student_number: 5002,
                  academic_year: 2026,
                  rn_year: 1,
                  _dbt_source_project: "kippnewark",
                }
              - {
                  studentid: 13,
                  student_number: 5001,
                  academic_year: 2026,
                  rn_year: 1,
                  _dbt_source_project: "kippcamden",
                }
          - input: ref("stg_focus__student_groups")
            rows:
              - {
                  id: 90,
                  title: "Bucket 2 - ELA",
                  end_date: null,
                  _dbt_source_project: "kippmiami",
                }
          - input: ref("stg_focus__students_join_groups")
            rows:
              - {
                  group_id: 90,
                  student_id: 84001234,
                  syear: 2026,
                  created_at: "2026-09-17 12:00:00",
                  _dbt_source_project: "kippmiami",
                }
        expect:
          rows:
            - {
                academic_year: 2026,
                region: "Newark",
                student_number: 5001,
                subject: "Math",
                bucket: "Bucket 3",
                bucket_store: "powerschool",
                n_active_assignments: 1,
              }
            - {
                academic_year: 2026,
                region: "Camden",
                student_number: 5001,
                subject: "Reading",
                bucket: "Bucket 1",
                bucket_store: "powerschool",
                n_active_assignments: 1,
              }
            - {
                academic_year: 2026,
                region: "Miami",
                student_number: 84001234,
                subject: "Reading",
                bucket: "Bucket 2",
                bucket_store: "focus",
                n_active_assignments: 1,
              }
```

Trim the `expect` rows' column lists if dbt requires every output column — unit
tests compare only the columns listed when `expect` uses partial rows (dbt >=
1.8 behavior; if the runner complains, add `assignment_date`).

- [ ] **Step 5: Run the unit test to green**

```bash
uv run dbt test --select int_students__bucket_assignments,test_type:unit \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Expected: PASS (3 expected rows, latest-wins on student 5001 Newark Math, MTSS
row excluded, cross-region 5001 rows separate).

- [ ] **Step 6: Build the model and run its data tests**

```bash
uv run dbt build --select int_students__bucket_assignments \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Expected: model builds; uniqueness and accepted_values pass; the
`n_active_assignments` warn test may WARN (real double uploads) — a warn here is
a finding to report, not a failure.

- [ ] **Step 7: Reconcile counts against the generator manifests (terminal
      only)**

Query per region x subject x bucket counts and compare with the committed
manifests in `TEAMSchools/academic-goal-setting`
(`config/goal_setting/manifests/ay2026/*.json`) for Miami, and with the NJ run
manifests once the NJ uploads land. Counts at upload time match; later deltas
are enrollment churn. Do not paste student-level rows anywhere.

- [ ] **Step 8: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/models/students/
git -C "$w" commit -m "feat(dbt): decode stored bucket assignments from PowerSchool and Focus"
```

---

### Task 4: Rewire the subjects roster onto the bucket model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_extracts__student_enrollments_subjects.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_extracts__student_enrollments_subjects.yml`

**Interfaces:**

- Consumes: Task 3's `int_students__bucket_assignments`;
  `base_powerschool__course_enrollments` (`cc_studentid`, `cc_yearid`,
  `illuminate_subject_area`, `sections_section_number`, `teacher_lastfirst`,
  `is_dropped_section`, `rn_student_year_illuminate_subject_desc`,
  `_dbt_source_project`).
- Produces: unchanged column `nj_student_tier` (same name, same NJ values, Miami
  now real); new columns `bucket_store string`, `course_section_number string`,
  `course_teacher_lastfirst string`. The rpt (Task 6) reads all four.

- [ ] **Step 1: Delete the inline decode**

Remove the `bucket_programs` and `bucket_dedupe` CTEs (the block from the
`-- trunk-ignore(sqlfluff/ST03)` comment above `bucket_programs as (` through
the closing `)` of the `bucket_dedupe` deduplicate call).

- [ ] **Step 2: Swap the join and add new columns**

Replace:

```sql
left join
    bucket_dedupe as b
    on co.studentid = b.studentid
    and co.academic_year = b.academic_year
    and co._dbt_source_project = b._dbt_source_project
    and sj.discipline = b.discipline
```

with:

```sql
left join
    {{ ref("int_students__bucket_assignments") }} as b
    on co.student_number = b.student_number
    and co.academic_year = b.academic_year
    and co.region = b.region
    and sj.iready_subject = b.subject
left join
    {{ ref("base_powerschool__course_enrollments") }} as cc
    on co.studentid = cc.cc_studentid
    and co.yearid = cc.cc_yearid
    and co._dbt_source_project = cc._dbt_source_project
    and sj.illuminate_subject_area = cc.illuminate_subject_area
    and not cc.is_dropped_section
    and cc.rn_student_year_illuminate_subject_desc = 1
```

The `nj_student_tier` expression is unchanged
(`if(b.bucket in ('Bucket 1', 'Bucket 2', 'Bucket 3'), b.bucket, 'Bucket 4')`).
Add to the select list, next to the other plain joined columns:

```sql
    b.bucket_store,

    cc.sections_section_number as course_section_number,
    cc.teacher_lastfirst as course_teacher_lastfirst,
```

Check `co.region`'s value domain before committing: the model's own
`where co.region != 'Miami'` usage elsewhere in the repo confirms bare names
(Newark/Camden/Paterson/Miami), which is what Task 3 emits.

- [ ] **Step 3: Document the new columns**

In the properties yml, add under `columns:`:

```yaml
- name: bucket_store
  description:
    Which system holds the stored bucket assignment (powerschool/focus); null
    when the student has no assignment.
- name: course_section_number
  description:
    Enrolled course section for the subject, from PowerSchool course enrollments
    (null for Miami).
- name: course_teacher_lastfirst
  description: Teacher of that course section (null for Miami).
```

- [ ] **Step 4: Build and verify NJ parity**

```bash
uv run dbt build --select int_extracts__student_enrollments_subjects \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Then verify (BigQuery, terminal only) that the NJ `nj_student_tier` distribution
is identical pre/post: compare `count(*) group by region, nj_student_tier` on
the dev build vs prod for `academic_year = 2026 and region != 'Miami'`.
Expected: identical counts per tier for NJ; Miami moves from all-Bucket 4 to a
real distribution.

- [ ] **Step 5: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/models/students/
git -C "$w" commit -m "feat(dbt): read stored buckets and course sections on the subjects roster"
```

---

### Task 5: `int_assessments__goal_benchmarks`

**Files:**

- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__goal_benchmarks.sql`
- Create:
  `src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__goal_benchmarks.yml`

**Interfaces:**

- Consumes: `int_assessments__state_scores`,
  `int_assessments__iready_diagnostic_results`, `stg_renlearn__star` (legal for
  a domain intermediate; kipptaf convention is to consume Star there).
- Produces: ref `int_assessments__goal_benchmarks`, one row per
  `student_number int64` x `academic_year int64` x `subject string`
  (Reading/Math), columns `benchmark_assessment_type string`,
  `performance_level int64`, `scale_score float64`, `scale_score_state float64`,
  `is_proficient_int_state int64`, `scale_score_iready float64`,
  `is_proficient_int int64`, `is_approaching_int int64`, `is_below_int int64`,
  `is_tested_int int64`. Task 6 reads it. The columns are display/comparison
  only; nothing classifies on them.

- [ ] **Step 1: Write the model**

Port the score-panel CTEs from `rpt_tableau__academic_goals_rollup.sql`
verbatim, then assemble with a full join instead of the enrollment spine:

```sql
with
    state_test_union as (
        select
            student_number,
            academic_year,
            scale_score,
            performance_level as `level`,

            if(
                score_source = 'state_nj', assessment_name, 'FAST PM3'
            ) as assessment_type,

            -- grade 3 FAST reads PM1 of the same year, not PM3 of the prior year
            academic_year + if(
                score_source = 'state_fl' and administration_period = 'PM1', 0, 1
            ) as academic_year_plus,

            is_proficient_int,
            is_approaching_int,
            is_below_int,
            raw_subject,
            source_system,

            illuminate_subject_area as `subject`,
        from {{ ref("int_assessments__state_scores") }}
        where
            (
                score_source = 'state_nj'
                and assessment_name = 'NJSLA'
                and not (grade_level_when_assessed = 8 and raw_subject like 'Algebra%')
            )
            or (
                score_source = 'state_fl'
                and assessment_name = 'FAST'
                and scale_score is not null
                and (
                    (administration_period = 'PM3' and test_grade != 3)
                    or (administration_period = 'PM1' and test_grade = 3)
                )
            )

        union all

        select
            student_display_id as student_number,

            academic_year,
            unified_score as scale_score,
            state_benchmark_category_level as `level`,

            'Star EOY' as assessment_type,

            academic_year + 1 as academic_year_plus,

            if(state_benchmark_category_level < 4, 1, 0) as is_proficient_int,
            if(state_benchmark_category_level = 4, 1, 0) as is_approaching_int,
            if(state_benchmark_category_level = 5, 1, 0) as is_below_int,

            cast(null as string) as raw_subject,
            cast(null as string) as source_system,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,
        from {{ ref("stg_renlearn__star") }}
        where
            rn_subject_round = 1
            and screening_period_window_name = 'Spring'
            and grade_level between 1 and 2
    ),

    state_test_ranked as (
        select
            student_number,
            academic_year_plus,
            scale_score,
            `level`,
            assessment_type,
            is_proficient_int,
            is_approaching_int,
            is_below_int,

            case
                when source_system is null
                then `subject`
                when `subject` = 'Text Study'
                then 'Reading'
                else 'Math'
            end as `subject`,
        from state_test_union
    ),

    state_test_picked as (
        select
            *,

            row_number() over (
                partition by student_number, academic_year_plus, `subject`
                order by scale_score desc
            ) as rn_state,
        from state_test_ranked
    ),

    iready_union as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,
            projected_level_number_typical as `level`,

            'i-Ready BOY' as assessment_type,

            overall_scale_score + annual_typical_growth_measure as scale_score,

            if(projected_is_proficient_typical, 1, 0) as is_proficient_int,

            case
                when region = 'KIPP Miami' and projected_level_number_typical = 2
                then 1
                when region != 'KIPP Miami' and projected_level_number_typical = 3
                then 1
                else 0
            end as is_approaching_int,

            case
                when region = 'KIPP Miami' and projected_level_number_typical < 2
                then 1
                when region != 'KIPP Miami' and projected_level_number_typical < 3
                then 1
                else 0
            end as is_below_int,
        from {{ ref("int_assessments__iready_diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null
            and student_grade_int between 3 and 8

        union all

        select
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,
            level_number_with_typical as `level`,

            'i-Ready BOY' as assessment_type,

            overall_scale_score + annual_typical_growth_measure as scale_score,

            if(level_number_with_typical >= 4, 1, 0) as is_proficient_int,
            if(level_number_with_typical = 3, 1, 0) as is_approaching_int,
            if(level_number_with_typical < 3, 1, 0) as is_below_int,
        from {{ ref("int_assessments__iready_diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null
            and student_grade_int in (0, 1, 2, 9)

        union all

        select
            student_display_id as student_number,
            academic_year,

            if(star_discipline = 'ELA', 'Reading', star_discipline) as `subject`,

            district_benchmark_category_level as `level`,

            'Star BOY' as assessment_type,

            unified_score as scale_score,

            if(district_benchmark_category_level = 1, 1, 0) as is_proficient_int,
            if(district_benchmark_category_level = 2, 1, 0) as is_approaching_int,
            if(district_benchmark_category_level >= 3, 1, 0) as is_below_int,
        from {{ ref("stg_renlearn__star") }}
        where
            rn_subject_round = 1
            and screening_period_window_name = 'Fall'
            and grade_level = 0
    ),

    iready_picked as (
        select
            *,

            row_number() over (
                partition by student_number, academic_year, `subject`
                order by if(assessment_type = 'Star BOY', 0, 1), scale_score desc
            ) as rn_iready,
        from iready_union
    )

select
    coalesce(st.student_number, ir.student_number) as student_number,
    coalesce(st.academic_year_plus, ir.academic_year) as academic_year,
    coalesce(st.subject, ir.subject) as `subject`,

    st.scale_score as scale_score_state,
    st.is_proficient_int as is_proficient_int_state,

    ir.scale_score as scale_score_iready,

    coalesce(st.level, ir.level) as performance_level,
    coalesce(st.scale_score, ir.scale_score) as scale_score,
    coalesce(st.is_proficient_int, ir.is_proficient_int) as is_proficient_int,
    coalesce(st.is_approaching_int, ir.is_approaching_int) as is_approaching_int,
    coalesce(st.is_below_int, ir.is_below_int) as is_below_int,
    coalesce(st.assessment_type, ir.assessment_type) as benchmark_assessment_type,

    if(
        st.scale_score is not null or ir.scale_score is not null, 1, 0
    ) as is_tested_int,
from state_test_picked as st
full join
    iready_picked as ir
    on st.student_number = ir.student_number
    and st.academic_year_plus = ir.academic_year
    and st.subject = ir.subject
    and ir.rn_iready = 1
where (st.rn_state = 1 or st.rn_state is null) and (ir.rn_iready = 1 or ir.rn_iready is null)
```

(The `rn` predicates sit in `where` with null-guards because a full join
preserves unmatched sides; if sqlfluff or review prefers it, filter each side to
`rn = 1` in its own CTE before the full join instead — equivalent and cleaner.)

- [ ] **Step 2: Write the properties yml with the unit test**

```yaml
models:
  - name: int_assessments__goal_benchmarks
    description: >-
      The benchmark-score panel shown beside stored bucket assignments: the
      prior-year state result (NJSLA / FAST PM3 / Star EOY, grade-3 FAST PM1
      same-year) with the i-Ready BOY typical-growth projection (Star BOY for
      Miami K) as fallback. One row per student x academic_year x subject.
      Display and comparison only - bucket membership never derives from these
      columns. Miami K reads the standard Star export until #5377 stages the
      FAST Star file.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - academic_year
            - student_number
            - subject
    columns:
      - name: benchmark_assessment_type
        description: NJSLA, FAST, FAST PM3, Star EOY, Star BOY, or i-Ready BOY.
      - name: is_tested_int
        description:
          1 when any benchmark source has a score; drives the Tableau
          denominator parameter.
    unit_tests:
      - name: unit_int_assessments__goal_benchmarks_miami_k_star_first
        description:
          A Miami K student with Star BOY and i-Ready rows gets one row, Star
          first.
        model: int_assessments__goal_benchmarks
        given:
          - input: ref("int_assessments__state_scores")
            rows: []
          - input: ref("int_assessments__iready_diagnostic_results")
            rows:
              - {
                  student_id: 84005678,
                  academic_year_int: 2026,
                  subject: "Math",
                  level_number_with_typical: 3,
                  projected_level_number_typical: null,
                  projected_is_proficient_typical: null,
                  projected_sublevel_number_typical: null,
                  sublevel_number_with_typical: 2,
                  overall_scale_score: 400,
                  annual_typical_growth_measure: 20,
                  region: "KIPP Miami",
                  test_round: "BOY",
                  rn_subj_round: 1,
                  student_grade_int: 0,
                }
          - input: ref("stg_renlearn__star")
            rows:
              - {
                  student_display_id: 84005678,
                  academic_year: 2026,
                  star_discipline: "Math",
                  district_benchmark_category_level: 2,
                  state_benchmark_category_level: null,
                  unified_score: 777,
                  rn_subject_round: 1,
                  screening_period_window_name: "Fall",
                  grade_level: 0,
                }
        expect:
          rows:
            - {
                student_number: 84005678,
                academic_year: 2026,
                subject: "Math",
                benchmark_assessment_type: "Star BOY",
                is_approaching_int: 1,
                is_tested_int: 1,
              }
```

Fixture columns must satisfy every column the model reads from each input — if
the parse complains about a missing column, add it to the fixture row with a
null.

- [ ] **Step 3: Run the unit test to green**

```bash
uv run dbt test --select int_assessments__goal_benchmarks,test_type:unit \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Expected: PASS.

- [ ] **Step 4: Build and run data tests**

```bash
uv run dbt build --select int_assessments__goal_benchmarks \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Expected: build green, grain test passes. If the uniqueness test fails, inspect
the duplicate keys (terminal only) — a real duplicate means a source grain
assumption broke; fix the pick windows, never add a masking distinct.

- [ ] **Step 5: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/models/assessments/
git -C "$w" commit -m "feat(dbt): relocate the goal benchmark score panel to an intermediate"
```

---

### Task 6: `rpt_tableau__academic_goals_dashboard`

**Files:**

- Create:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__academic_goals_dashboard.sql`
- Create:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__academic_goals_dashboard.yml`

**Interfaces:**

- Consumes: Task 4's roster columns (`nj_student_tier`, `bucket_store`,
  `course_section_number`, `course_teacher_lastfirst`, plus existing roster
  columns), Task 5's `int_assessments__goal_benchmarks`,
  `int_assessments__academic_goals` (`school_id`, `academic_year`,
  `grade_level`, `illuminate_subject_area`, six goal columns).
- Produces: the workbook's one datasource. Contract-enforced; grain
  academic_year x student_number x subject.

- [ ] **Step 1: Write the model**

```sql
select
    co.academic_year,
    co.region,
    co.schoolid,
    co.school,
    co.grade_level,
    co.student_number,
    co.student_name,
    co.iep_status,
    co.team as homeroom_section,
    co.advisor_lastfirst as homeroom_teacher_name,
    co.course_section_number as course_section,
    co.course_teacher_lastfirst as course_teacher_name,
    co.iready_subject as `subject`,
    co.nj_student_tier as student_tier,
    co.bucket_store,

    gb.performance_level,
    gb.scale_score,
    gb.scale_score_state,
    gb.is_proficient_int_state,
    gb.scale_score_iready,
    gb.is_proficient_int as is_proficient_live_int,
    gb.is_approaching_int as is_approaching_live_int,
    gb.is_below_int as is_below_live_int,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,
    g.grade_band_goal,
    g.assessment_band_goal,

    coalesce(gb.benchmark_assessment_type, 'Untested') as benchmark_assessment_type,
    coalesce(gb.is_tested_int, 0) as is_tested_int,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
left join
    {{ ref("int_assessments__goal_benchmarks") }} as gb
    on co.student_number = gb.student_number
    and co.academic_year = gb.academic_year
    and co.iready_subject = gb.subject
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on co.schoolid = g.school_id
    and co.academic_year = g.academic_year
    and co.grade_level = g.grade_level
    and co.illuminate_subject_area = g.illuminate_subject_area
where co.academic_year >= 2026 and co.rn_year = 1 and co.enroll_status = 0
```

Before writing, confirm the roster exposes `schoolid` and `student_name`
(`grep -n "schoolid\|student_name" <the subjects properties yml>`); if the
roster's school id column is named differently (`reporting_schoolid`), use the
plain `schoolid` — the goals sheet rows are per actual school.

- [ ] **Step 2: Write the properties yml**

Contract-enforced with every column typed, uniqueness on the grain, and a unit
test pinning Review Focus items 3 and 5:

```yaml
models:
  - name: rpt_tableau__academic_goals_dashboard
    description: >-
      Student-grain datasource for the Academic Goal Roll-Up workbook (all four
      tabs, all four regions). Joins only: the subjects roster (stored bucket,
      Bucket 4 default), the benchmark-score comparison panel, and the
      goals-sheet permutations. Official rollup measures aggregate student_tier
      in Tableau; is_tested_int drives the denominator parameter. Scoped to
      academic_year >= 2026 - SY26 stays on the disabled
      rpt_tableau__academic_goals_rollup relation.
    config:
      contract:
        enforced: true
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns:
            - academic_year
            - student_number
            - subject
    columns:
      - name: academic_year
        data_type: int64
      - name: region
        data_type: string
      - name: schoolid
        data_type: int64
      - name: school
        data_type: string
      - name: grade_level
        data_type: int64
      - name: student_number
        data_type: int64
      - name: student_name
        data_type: string
      - name: iep_status
        data_type: string
      - name: homeroom_section
        data_type: string
      - name: homeroom_teacher_name
        data_type: string
      - name: course_section
        data_type: string
      - name: course_teacher_name
        data_type: string
      - name: subject
        data_type: string
      - name: student_tier
        data_type: string
        data_tests:
          - accepted_values:
              values: ["Bucket 1", "Bucket 2", "Bucket 3", "Bucket 4"]
      - name: bucket_store
        data_type: string
      - name: performance_level
        data_type: int64
      - name: scale_score
        data_type: float64
      - name: scale_score_state
        data_type: float64
      - name: is_proficient_int_state
        data_type: int64
      - name: scale_score_iready
        data_type: float64
      - name: is_proficient_live_int
        data_type: int64
      - name: is_approaching_live_int
        data_type: int64
      - name: is_below_live_int
        data_type: int64
      - name: grade_goal
        data_type: float64
      - name: school_goal
        data_type: float64
      - name: region_goal
        data_type: float64
      - name: organization_goal
        data_type: float64
      - name: grade_band_goal
        data_type: float64
      - name: assessment_band_goal
        data_type: float64
      - name: benchmark_assessment_type
        data_type: string
      - name: is_tested_int
        data_type: int64
    unit_tests:
      - name: unit_rpt_academic_goals_dashboard_defaults
        description: >-
          An enrolled student with no stored bucket and no benchmark lands as
          Bucket 4 / Untested, and a missing goal row keeps the student with
          null goals.
        model: rpt_tableau__academic_goals_dashboard
        given:
          - input: ref("int_extracts__student_enrollments_subjects")
            rows:
              - {
                  academic_year: 2026,
                  region: "Newark",
                  schoolid: 73254,
                  school: "SPARK",
                  grade_level: 3,
                  student_number: 5003,
                  student_name: "Student, New",
                  iep_status: "No IEP",
                  team: "3A",
                  advisor_lastfirst: "Teacher, A",
                  course_section_number: null,
                  course_teacher_lastfirst: null,
                  iready_subject: "Math",
                  illuminate_subject_area: "Mathematics",
                  nj_student_tier: "Bucket 4",
                  bucket_store: null,
                  rn_year: 1,
                  enroll_status: 0,
                }
          - input: ref("int_assessments__goal_benchmarks")
            rows: []
          - input: ref("int_assessments__academic_goals")
            rows: []
        expect:
          rows:
            - {
                academic_year: 2026,
                student_number: 5003,
                subject: "Math",
                student_tier: "Bucket 4",
                benchmark_assessment_type: "Untested",
                is_tested_int: 0,
                school_goal: null,
                grade_band_goal: null,
              }
```

The data type of `performance_level`/goal columns must match the upstream
reality — if the contract build fails on a type, fix the yml type to the
upstream's (`float64` vs `int64`), never cast in the rpt.

- [ ] **Step 3: Run unit test, then build with data tests**

```bash
uv run dbt test --select rpt_tableau__academic_goals_dashboard,test_type:unit \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
uv run dbt build --select rpt_tableau__academic_goals_dashboard \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 15
```

Expected: both green.

- [ ] **Step 4: Sanity-check the AY2026 output (terminal only)**

Aggregate checks in BigQuery against the dev build — counts only, no student
rows:

1. Per region x grade band: Bucket 1 share and
   `count(distinct student_number) where student_tier = 'Bucket 2'` versus the
   old view's `student_tier_calculated` distribution. Known deltas are where the
   old CASE diverges from the generator (that divergence is the point).
2. Goal columns non-null for every K-2 and 3-8 NJ row (the sheet rows exist);
   null for grade 9 (not yet loaded) — matches expectation.

- [ ] **Step 5: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/models/extracts/tableau/
git -C "$w" commit -m "feat(dbt): joins-only academic goals dashboard view"
```

---

### Task 7: Retire the old view, baseline rows, exposure

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__academic_goals_rollup.yml`
- Modify: `src/dbt/kipptaf/standard-baseline.tsv`
- Modify: `src/dbt/kipptaf/models/exposures/tableau.yml`

**Interfaces:**

- Consumes: Task 6's model name.
- Produces: the disabled SY26 record and the workbook exposure.

- [ ] **Step 1: Disable the old view**

In `rpt_tableau__academic_goals_rollup.yml`, add under the model:

```yaml
config:
  enabled: false
```

and add `config: {enabled: false}` to every test listed in that file (disabling
a model does not disable its tests). Do not touch the `.sql`.

- [ ] **Step 2: Remove its baseline rows**

Delete these two lines from `src/dbt/kipptaf/standard-baseline.tsv`:

```text
kipptaf.rpt_tableau__academic_goals_rollup	A1	kipptaf.base_powerschool__course_enrollments	#5812
kipptaf.rpt_tableau__academic_goals_rollup	A1	kipptaf.stg_renlearn__star	#5812
```

- [ ] **Step 3: Add the exposure**

In `models/exposures/tableau.yml`, alphabetically placed:

```yaml
- name: academic_goal_rollup_dashboard
  label: Academic Goal Roll-Up
  type: dashboard
  owner:
    name: Data Team - awalters
  depends_on:
    - ref("rpt_tableau__academic_goals_dashboard")
  config:
    meta:
      dagster:
        kinds:
          - tableau
        asset:
          metadata:
            id: 15cb4859-ab6d-46a7-8e4f-1aa786785aa3
```

No `cron_schedule`: the workbook refresh is not Dagster-managed.

- [ ] **Step 4: Parse and verify the node delta**

```bash
uv run dbt parse --no-partial-parse --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 5
```

Expected: parse succeeds; `rpt_tableau__academic_goals_rollup` and its tests are
no longer in the manifest
(`grep -c academic_goals_rollup "$w/src/dbt/kipptaf/target/manifest.json"` drops
to source-mention counts only).

- [ ] **Step 5: Commit**

```bash
git -C "$w" add src/dbt/kipptaf/
git -C "$w" commit -m "feat(dbt): retire the recomputing goals rollup and register the workbook exposure"
```

---

### Task 8: Full-chain verification and PR

**Files:**

- No new files; runs builds, lint, and opens the PR.

**Interfaces:**

- Consumes: everything above.

- [ ] **Step 1: Build the whole chain plus downstream**

```bash
uv run dbt build \
  --select int_students__bucket_assignments+ int_assessments__goal_benchmarks+ \
  --project-dir "$w/src/dbt/kipptaf" 2>&1 | tail -n 30
```

The `+` pulls the rewired roster's ~15 downstream consumers — expect latent
warn-severity noise unrelated to this change (check any failure against prod
before attributing it; see `src/dbt/kipptaf/CLAUDE.md` -> dbt Cloud CI).

- [ ] **Step 2: Lint every changed file**

```bash
cd "$w" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C "$w" diff --name-only origin/main -- 'src/dbt/*' 'docs/*') </dev/null
```

Fix findings; formatting is the commit hook's job.

- [ ] **Step 3: Push and open the PR**

Body from `.github/pull_request_template.md`. Summary in plain language; the
Reviewer Notes name: (1) the intermediates rationale section of the spec, (2)
the Miami `nj_student_tier` value change across its consumers, (3) the
baseline-row removal. "For Claude" fold-out carries the reconciliation numbers
(aggregates only). `Closes #5890` in the body. Per A2, file the missing-marts
issue (buckets/goals/subject roster have no mart) and link it in the PR body
before opening. End the body with the repo's PR attribution line.

```bash
git -C "$w" push -u origin anthonygwalters/feat/claude-goals-dashboard-view
```

Then `mcp__github__create_pull_request` with base `main`. After opening, offer
CI watch and claude-review response per the root CLAUDE.md.

- [ ] **Step 4: Post-merge handoffs (not part of this PR)**

Record in the PR body's "For Claude" section: after prod materializes, run the
manifest reconciliations (spec -> Verification), then the workbook repoint in
Tableau Desktop (four tabs onto the new extract, delete `miami_goals_new`),
publish, and verify side by side before unpublishing the old extract.
