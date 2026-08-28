# Focus Identity Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore KIPP Miami to the kipptaf network layer for AY2026 by adding a
Focus branch to the seven models that carry student, school, and enrollment
identity.

**Architecture:** Every kipptaf model in scope is a thin
`dbt_utils.union_relations` wrapper over per-district sources. Miami's branch
currently points at the frozen `kippmiami_powerschool` archive. This plan adds a
conforming `int_focus__*_conformed` model per spine model — holding the unprefix
rule and the value translations — and unions it in. Intermediate-layer models
take the Focus branch in place; staging-layer models get a new SIS-agnostic
`int_students__*` sibling whose mart consumers are repointed onto
`student_number`, retiring the PowerSchool DCID joins those marts inherited.

**Tech Stack:** dbt 1.11 on BigQuery, `dbt_utils.union_relations`, `uv` for all
Python/dbt invocation, trunk for lint.

**Design spec:**
[`docs/superpowers/specs/2026-08-04-focus-identity-spine-design.md`](../specs/2026-08-04-focus-identity-spine-design.md)

**Issue:** [#4731](https://github.com/TEAMSchools/teamster/issues/4731)

## Global Constraints

These apply to every task. They are not repeated per-task.

- **Worktree.** All work happens in
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine`.
  Every git call uses `git -C <worktree>`; every dbt call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. A bare `git` from the main repo
  commits to `main`.
- **Never re-derive `_dbt_source_project`.** It is pass-through, produced only
  at the `union_relations` view that creates `_dbt_source_relation`. New union
  models in this plan pass `source_column_name=none` so both columns survive
  from upstream intact. Re-deriving with `extract_source_project()` at a
  kipptaf-over-kipptaf union yields `kipptaf` for every row and silently breaks
  region resolution.
- **`extract_region(t)` reads `t._dbt_source_project`**, not
  `_dbt_source_relation` (`src/dbt/kipptaf/macros/utils.sql:7`).
- **The Miami archive must be excluded** from the PowerSchool side of every new
  union, or Miami students appear twice. Filter on `_dbt_source_relation`.
  Exception: `int_powerschool__student_enrollment_union`, which retains the
  archive's alumni placeholders — see Task 8.
- **Column vocabulary is PowerSchool's.** No mart output column changes, so no
  Cube updates. Renaming to the source-agnostic vocabulary is Phase 5.
- **Every new model needs** a `properties.yml` with a `description:` on the
  model and every column, plus a uniqueness test (intermediate-layer
  requirement).
- **`config.meta.contains_pii` does not travel through `source()`** — re-declare
  it on every wrapper over a PII-carrying model.
- **Status fields carry forward.** `spedlep`, `lunchstatus`, and `lep_status`
  have no usable Focus source. Returning students take the archive value; new
  students get `null`, never a fabricated default. Each gets a warn-severity
  null test.
- **Lint before pushing.** `trunk fmt` runs at commit; sqlfluff and yamllint
  fire only at pre-push and CI. Run
  `~/.cache/trunk/launcher/trunk check --force --no-fix <files> </dev/null` from
  inside the worktree before any push.
- **PII stays local.** Validation queries return student-level rows. Keep values
  in `.claude/scratch/`; reference counts and column names in PRs and issues,
  never values.
- **sqlfluff ST06 buckets `cast()` as a SIMPLE target, not a calculation.** A
  `cast(...) as x` placed after `date(...)` / `regexp_extract(...)` in the same
  select list fails ST06 ("Select wildcards then simple targets before
  calculations"), even though the repo's written column-order convention reads
  as though nested functions go last. Put every `cast()` immediately after the
  plain column refs and before any other function call. Hit and confirmed in
  Task 2; the rule fires only at `trunk check --force`, never at build.
- **`--target staging` compiles empty for the new Focus models.** Confirmed in
  Task 1: `zz_stg_kippmiami_focus` holds none of the models #4725 shipped, so a
  `union_relations` wrapper over them expands to
  `/* No columns from any of the relations. */` and still exits clean. To verify
  a new wrapper actually resolves columns, compile against `--target prod`
  instead — `dbt compile` and `dbt parse` are not warehouse writes and are not
  classifier-blocked, unlike `dbt build --target prod`. Read the compiled SQL
  and confirm a real `cast(...) as ...` list. The staging copies get refreshed
  once, by the user, in Task 11 Step 6; until then treat every staging compile
  as uninformative rather than as a pass.

## Traps hit during implementation

Every one of these produced a silent wrong answer or a build failure in Tasks
1-8. Assume they apply to the remaining tasks.

- **Focus's `schoolid` is its own internal id** (14, 15, 58...), not the network
  school number. The network id is `ps_schoolid`, which the upstream already
  resolves through the locations crosswalk. Task 6 nearly shipped the Focus code
  as `school_number`, which would have null-filled every Miami school join with
  no error.
- **Same column name, different concept.** Focus `fteid` holds a Florida
  education identifier string (`FL000007024992`); the network `fteid` is a
  PowerSchool numeric id. The cast fails outright, and `safe_cast` would null
  real data under a misleading heading. Drop such columns and let the union
  null-fill them rather than forcing a conversion.
- **A view build does not evaluate the data.** A bad `cast` in a
  view-materialized conform model passes `dbt build` and only fails when a
  downstream TABLE materializes it. Do not read a green view build as validation
  of values.
- **`_dbt_source_project` must coalesce through from a kipptaf-level Focus
  branch.** The conform models are kipptaf relations, so the usual
  `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` reads `kipptaf` from
  them. Project `_dbt_source_project` on the conform model and
  `coalesce(_dbt_source_project, <regex>)` at the union.
- **BigQuery rejects `\_` in a string literal** (`Illegal escape sequence`). The
  branch discriminator is `like '%\\_focus%'`.
- **sqlfluff ST06 buckets `cast()` as a SIMPLE target** — casts go after plain
  column refs but BEFORE any other function call in the same select list.
- **Put the `AM04` trunk-ignore on the CTE that actually stars**, not the final
  select. A misplaced ignore fails twice: AM04 still fires, and
  `trunk/ignore-does-nothing` flags the stray directive.
- **Dev-target `sources-kipp*` resolve to `zz_<user>_*`, your personal copies.**
  `--favor-state` governs refs, not sources, so a stale personal copy silently
  produces a fake dev-vs-prod delta. Task 8's NJ counts looked like a 7,000-row
  regression that was entirely stale dev sources. Validate a filter change by
  comparing built rows against the SOURCE rows the build actually read, not
  against prod.
- **The hand-written `UNION ALL` from the plan's drafts needs EXPLICIT matching
  column lists** in both branches. Branch column counts differ, `UNION ALL` is
  positional, and repo sqlfluff CV03 forbids `select *` inside a UNION branch.
  Prefer adding the conform model as another relation in `union_relations`,
  which null-fills the superset automatically.

## Key facts verified against prod

Do not re-derive these; they are settled.

| Fact                                                                        | Value                                    |
| --------------------------------------------------------------------------- | ---------------------------------------- |
| `int_focus__students` grain                                                 | 1 row per `student_id`, 3,938 rows       |
| Unprefixing `8400` is injective                                             | 3,938 distinct in, 3,938 out, 0 failures |
| Unprefixed id matches archive `student_number`                              | 3,453 of 3,453 archive students          |
| `int_focus__students.powerschool_id` equals archive `student_number`        | 3,453 rows; null for new students        |
| Collisions between new Miami numbers and NJ numbers                         | 0                                        |
| `union_relations` builds a column **superset**, null-filling absent columns | `dbt_utils/macros/sql/union.sql:113`     |

## The DCID problem, and why the fix is to remove it

The spec says PowerSchool-only columns "resolve to null for Miami with no
special handling." For `dcid` that is currently false, and the failure is
silent. Four mart joins depend on it:

```text
dim_students.sql:73              on s.dcid = suf.studentsdcid
dim_students.sql:77              on s.dcid = njs.studentsdcid
dim_student_ell_status.sql:108   on e.students_dcid = scf.studentsdcid
dim_student_iep_status.sql:156   on e.students_dcid = scf.studentsdcid
```

`null = null` is false in SQL, so a null DCID yields **zero** Miami rows in
`dim_student_ell_status` and `dim_student_iep_status`, and null `fleid` in
`dim_students` — with no error raised.

**Minting a synthetic DCID for Miami would be the wrong fix.** `dcid` is a
PowerSchool-internal surrogate that the marts rubric already prohibits:

- **R2** lists `dcid` among the source-system terms marts must not use.
- **R7** says source-system acronyms like `dcid` are spelled out or removed.
- The plumbing definition names "PowerSchool `dcid`" as an internal row ID used
  only for upstream joins, and rules that plumbing stays in `staging/` and
  `intermediate/`.

Inventing a Focus DCID would spread a prohibited identifier into a second SIS to
satisfy a join that should not exist. The join is the defect.

**The fix: resolve `studentsdcid` to `student_number` in the intermediate layer,
and join the marts on `student_number`.** The two staging models carry only
`studentsdcid` — verified, neither has a `student_number` column — so the new
`int_students__student_core_fields` and `int_students__student_user_fields` do
that translation once, at exactly the layer the rubric says plumbing belongs in,
and expose `student_number` as the join key.

Three consequences:

- **Focus needs no synthetic key.** Its rows carry their real `student_number`,
  and `dcid` stays null for Miami exactly as the spec said.
- **The one remaining `dcid` join is correct as-is.** `dim_students.sql:77`
  joins `stg_powerschool__s_nj_stu_x`, an NJ-only table. Miami legitimately
  matches nothing there, so a null Miami `dcid` is the right answer. Leave that
  join alone — changing it risks NJ parity for no Miami benefit.
- **`int_students__students` still carries `dcid`** for that NJ join. It is an
  intermediate, which is where plumbing is allowed to live.

This removes a live rubric violation rather than working around it, and it
shrinks the change: the conform models become passthroughs on the canonical
identifier.

**`powerschool_id` is a free invariant check.** Focus carries the archive
`student_number` directly on returning students. Task 2 adds a warn test
asserting it agrees with the unprefixed id, which catches a prefix-rule
regression the moment it appears.

---

### Task 1: Declare and wrap the three missing Focus models

`stg_focus__co_teachers`, `stg_focus__students_join_users`, and
`int_focus__schedule` shipped in #4725 but are not declared at kipptaf level.
Task 10 needs all three. Per `kipptaf/CLAUDE.md`, every source added to a
`sources-kipp*.yml` needs a matching `union_relations` passthrough, and
consumers read the wrapper, not the source.

**Files:**

- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create: `src/dbt/kipptaf/models/focus/staging/stg_focus__co_teachers.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/stg_focus__students_join_users.sql`
- Create: `src/dbt/kipptaf/models/focus/intermediate/int_focus__schedule.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__co_teachers.yml`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__students_join_users.yml`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__schedule.yml`

**Interfaces:**

- Produces: three kipptaf models named exactly as their sources, each carrying
  `_dbt_source_relation` and `_dbt_source_project`. Task 10 consumes all three.

- [ ] **Step 1: Read the existing source file and one wrapper to copy the
      shape**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
cat src/dbt/kipptaf/models/focus/sources-kippmiami.yml
cat src/dbt/kipptaf/models/focus/staging/stg_focus__students.sql
```

- [ ] **Step 2: Append the three source entries**

Add to the `tables:` list in `sources-kippmiami.yml`, matching the existing
indentation exactly:

```yaml
- name: stg_focus__co_teachers
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - stg_focus__co_teachers
- name: stg_focus__students_join_users
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - stg_focus__students_join_users
- name: int_focus__schedule
  config:
    meta:
      dagster:
        group: focus
        asset_key:
          - kippmiami
          - focus
          - int_focus__schedule
```

- [ ] **Step 3: Write the three wrapper models**

`stg_focus__co_teachers.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[source("kippmiami_focus", "stg_focus__co_teachers")]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

`stg_focus__students_join_users.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "stg_focus__students_join_users"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

`int_focus__schedule.sql`:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__schedule"),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 4: Write the three properties files**

Get the authoritative column list first — do not hand-transcribe:

```sql
select column_name, data_type
from `teamster-332318.kippmiami_focus.INFORMATION_SCHEMA.COLUMNS`
where table_name in (
    'stg_focus__co_teachers', 'stg_focus__students_join_users', 'int_focus__schedule'
)
order by table_name, ordinal_position
```

Each properties file needs a model `description:`, a `description:` per column,
and a uniqueness test. `stg_focus__students_join_users` carries student and
staff ids, so set `config: meta: contains_pii: true` at model level. Model-level
suffices for a `select *` passthrough. Shape:

```yaml
models:
  - name: stg_focus__co_teachers
    description: >-
      Passthrough of the focus package co-teacher assignments, exposing Miami
      co-teaching relationships at network level for teacher rostering.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - course_period_id
              - staff_id
    columns:
      - name: course_period_id
        description: Focus identifier for the course period being co-taught.
```

- [ ] **Step 5: Verify the wrappers compile against the staging relations**

A dev-target compile expands to nothing (the `zz_<user>_*` dataset holds no
copy). Use `--target staging`, which resolves against the same `zz_stg_*`
relations dbt Cloud CI reads and is not a warehouse write.

```bash
cd /workspaces/teamster
uv run dbt compile \
  --select stg_focus__co_teachers stg_focus__students_join_users int_focus__schedule \
  --target staging \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: PASS. Then read the compiled SQL and confirm real column names were
listed — an empty expansion still compiles clean, so a clean exit is not proof:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
head -30 src/dbt/kipptaf/target/compiled/kipptaf/models/focus/intermediate/int_focus__schedule.sql
```

Expected: an explicit `cast(...) as ...` list, not a bare `*`.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
~/.cache/trunk/launcher/trunk check --force --no-fix \
  src/dbt/kipptaf/models/focus/sources-kippmiami.yml \
  src/dbt/kipptaf/models/focus/staging/stg_focus__co_teachers.sql \
  src/dbt/kipptaf/models/focus/staging/stg_focus__students_join_users.sql \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__schedule.sql </dev/null
```

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/
git -C "$wt" commit -m "feat(dbt): expose the three unwrapped Focus models at kipptaf level

Refs #4731"
```

---

### Task 2: `int_focus__students_conformed`

The core of the plan. Every other conform model reuses its identity rule.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__students_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__students_conformed.yml`

**Interfaces:**

- Consumes: `ref("int_focus__students")` (existing wrapper),
  `ref("stg_powerschool__students")` (archive carry-forward).
- Produces: a relation with PowerSchool column names — `student_number INT64`,
  `first_name`, `middle_name`, `last_name`, `dob DATE`, `gender STRING`,
  `ethnicity STRING`, `enroll_status INT64`, `lep_status BOOL`,
  `spedlep STRING`, `lunchstatus STRING`, `cohort INT64`, plus
  `_dbt_source_relation` and `_dbt_source_project` passed through. Tasks 3, 5,
  and 6 consume it.

- [ ] **Step 1: Confirm the archive's ethnicity domain before writing the
      mapping**

The mapping must reproduce the archive's values, so read them first rather than
assuming the PowerSchool code set:

```sql
select ethnicity, count(*) as students
from `teamster-332318.kippmiami_powerschool.stg_powerschool__students`
group by ethnicity
order by students desc
```

Record the result. The `case` in Step 3 must produce exactly this domain.

- [ ] **Step 2: Write the failing reconciliation test**

Write the test before the model, so it fails for the right reason. Create
`src/dbt/kipptaf/tests/test_focus_students_conformed_matches_archive.sql`:

```sql
-- Returning Miami students must conform to the values the frozen archive
-- carried. This is the only real test of the identity and value translations,
-- and it is possible only because Focus covers AY2018 through AY2026.
select
    c.student_number,
    c.ethnicity as conformed_ethnicity,
    a.ethnicity as archive_ethnicity,
    c.gender as conformed_gender,
    a.gender as archive_gender,
    c.dob as conformed_dob,
    a.dob as archive_dob,
from {{ ref("int_focus__students_conformed") }} as c
inner join
    {{ ref("stg_powerschool__students") }} as a
    on c.student_number = a.student_number
    and a._dbt_source_project = 'kippmiami'
where
    c.ethnicity is distinct from a.ethnicity
    or c.gender is distinct from a.gender
    or c.dob is distinct from a.dob
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd /workspaces/teamster
uv run dbt parse \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: FAIL with
`Model 'model.kipptaf.int_focus__students_conformed' not found`.

- [ ] **Step 4: Write the conform model**

```sql
with
    -- The unprefixed Focus student id is the canonical network student number.
    -- Strip a leading 8400 (Miami-Dade's FLDOE district number) where present;
    -- pass any other value through unchanged rather than guessing at a
    -- different prefix, so the one known anomalous id stays visible instead of
    -- being silently mangled.
    identified as (
        select
            *,

            cast(
                regexp_replace(cast(student_id as string), r'^8400', '') as int64
            ) as student_number,
        from {{ ref("int_focus__students") }}
    ),

    -- spedlep, lunchstatus, and lep_status have no usable Focus source: Focus
    -- ese_fefp_code is an FEFP funding code covering 162 of 419 archive SPED
    -- students, free_reduced_meals_program is a single school-wide CEP
    -- constant, and english_language_learner_pk_12 puts 98% of students at ZZ.
    -- Carry the archive value forward for returning students; new students get
    -- null. A false negative on IEP status is compliance-adjacent, and a
    -- fabricated FRL or ELL value feeds an economic-disadvantage proxy.
    archive as (
        select
            student_number,
            spedlep,
            lunchstatus,
            lep_status,
        from {{ ref("stg_powerschool__students") }}
        where _dbt_source_project = 'kippmiami'
    ),

    conformed as (
        select
            i._dbt_source_relation,
            i._dbt_source_project,
            i.student_number,
            i.first_name,
            i.middle_name,
            i.last_name,
            i.powerschool_id,
            i.florida_student_number,
            i.florida_education_identifier,
            i.year_entered_ninth_grade,
            i.single_ethnicity,
            i.ethnicity_hispanic_or_latino,
            i.race_black_or_african_american,
            i.race_white,
            i.race_asian,
            i.race_american_indian_or_alaska_native,
            i.race_native_hawaiian_or_other_pacific_islander,

            a.spedlep,
            a.lunchstatus,
            a.lep_status,

            -- No dcid is projected. It is a PowerSchool-internal surrogate the
            -- marts rubric prohibits (R2, R7, plumbing), and the joins that
            -- needed it are moved to student_number in Tasks 4 and 5. It
            -- null-fills for Miami, which is correct.
            date(i.birthdate) as dob,

            i.sex_label as gender_label,

            (
                i.race_black_or_african_american
                + i.race_white
                + i.race_asian
                + i.race_american_indian_or_alaska_native
                + i.race_native_hawaiian_or_other_pacific_islander
            ) as race_count,
        from identified as i
        left join archive as a on i.student_number = a.student_number
    )

select
    _dbt_source_relation,
    _dbt_source_project,
    student_number,
    first_name,
    middle_name,
    last_name,
    dob,
    spedlep,
    lunchstatus,
    lep_status,
    powerschool_id,
    florida_student_number,
    florida_education_identifier,

    if(left(gender_label, 1) in ('M', 'F'), left(gender_label, 1), null) as gender,

    -- Cohort is the graduation year, derived from the year the student entered
    -- ninth grade. Null for K-8, which never enters ninth grade.
    if(
        year_entered_ninth_grade > 0, year_entered_ninth_grade + 4, null
    ) as cohort,

    case
        when ethnicity_hispanic_or_latino = 1
        then 'H'
        when race_count > 1
        then 'T'
        when race_black_or_african_american = 1
        then 'B'
        when race_white = 1
        then 'W'
        when race_asian = 1
        then 'A'
        when race_american_indian_or_alaska_native = 1
        then 'I'
        when race_native_hawaiian_or_other_pacific_islander = 1
        then 'P'
    end as ethnicity,

from conformed
```

- [ ] **Step 5: Build it and run the reconciliation test**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__students_conformed \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: PASS on the build. The reconciliation test will likely FAIL on first
run — that is the point of the task. Read the failing rows and correct the
`case` in Step 4 until it passes. Do not weaken the test to make it pass; the
archive's values are the specification.

- [ ] **Step 6: Add the properties file with tests**

```yaml
models:
  - name: int_focus__students_conformed
    description: >-
      Miami student identity from Focus, conformed to PowerSchool column names
      and value domains so it can union into the network student spine. Holds
      the unprefix rule and the value translations. Statuses with no usable
      Focus source carry forward from the frozen PowerSchool archive for
      returning students and are null for students new since the freeze.
    config:
      meta:
        contains_pii: true
    columns:
      - name: student_number
        description: >-
          Canonical network student number, the Focus student id with its
          leading 8400 Miami-Dade district prefix removed.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: spedlep
        description: >-
          IEP classification carried forward from the frozen PowerSchool
          archive. Null for students new since the freeze, because Focus ESE
          fields are not yet populated.
        data_tests:
          - not_null:
              config:
                severity: warn
      - name: lunchstatus
        description: >-
          Meal eligibility carried forward from the frozen PowerSchool archive.
          Null for students new since the freeze, because Focus records
          school-wide CEP eligibility rather than per-student status.
        data_tests:
          - not_null:
              config:
                severity: warn
      - name: lep_status
        description: >-
          English learner status carried forward from the frozen PowerSchool
          archive. Null for students new since the freeze, because the Focus ELL
          field is effectively unpopulated.
        data_tests:
          - not_null:
              config:
                severity: warn
      - name: ethnicity
        description: >-
          Single-character race and ethnicity code matching the domain the
          PowerSchool archive carried, derived from the Focus race flags.
          Hispanic takes precedence, then multiracial, then the single flagged
          race.
      - name: first_name
        description: Student's legal first name as recorded in Focus.
      - name: middle_name
        description: Student's legal middle name as recorded in Focus.
      - name: last_name
        description: Student's legal last name as recorded in Focus.
      - name: dob
        description: Date of birth, cast from the Focus birthdate timestamp.
      - name: gender
        description: >-
          Single-character gender code derived from the Focus sex label,
          matching the archive domain.
      - name: cohort
        description: >-
          Expected graduation year, derived as year entered ninth grade plus
          four. Null for K-8 students, who have no ninth-grade entry year.
      - name: powerschool_id
        description: >-
          Archive student number as Focus recorded it. Populated only for
          students who predate the SIS migration; used to verify the unprefix
          rule, not as a join key.
      - name: florida_student_number
        description: Florida state student number as recorded in Focus.
      - name: florida_education_identifier
        description: FLEID, the Florida statewide education identifier.
      - name: _dbt_source_relation
        description: Source relation, passed through from the Focus wrapper.
      - name: _dbt_source_project
        description:
          District code location, passed through from the Focus wrapper.
```

- [ ] **Step 7: Add the unprefix-rule invariant test**

Focus carries the archive student number on returning students, so the unprefix
rule can be checked against it directly. Create
`src/dbt/kipptaf/tests/test_focus_unprefix_rule_holds.sql`:

```sql
-- Focus records the pre-migration student number on returning students. If the
-- unprefixed id disagrees with it, the prefix rule has regressed. Warn rather
-- than error: the one known anomalous id (a 10-digit value with no 8400
-- prefix) is passed through deliberately and is an Ops correction, not a bug.
{{ config(severity="warn") }}

select student_number, powerschool_id,
from {{ ref("int_focus__students_conformed") }}
where powerschool_id is not null and cast(powerschool_id as int64) != student_number
```

- [ ] **Step 8: Run the full test set, lint, and commit**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__students_conformed \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: PASS, with the three status `not_null` tests reporting WARN and naming
a count close to the 485 students new since the freeze.

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
~/.cache/trunk/launcher/trunk check --force --no-fix \
  src/dbt/kipptaf/models/focus/intermediate/int_focus__students_conformed.sql \
  src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__students_conformed.yml \
  src/dbt/kipptaf/tests/test_focus_students_conformed_matches_archive.sql \
  src/dbt/kipptaf/tests/test_focus_unprefix_rule_holds.sql </dev/null
```

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/intermediate/ src/dbt/kipptaf/tests/
git -C "$wt" commit -m "feat(dbt): conform Focus student identity to the network spine

Refs #4731"
```

---

### Task 3: `int_students__students` and repoint `dim_students`

**Files:**

- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__students.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__students.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_students.sql:5`

**Interfaces:**

- Consumes: `ref("stg_powerschool__students")`,
  `ref("int_focus__students_conformed")` from Task 2.
- Produces: `int_students__students`, the SIS-agnostic student spine.
  `dim_students` consumes it. Carries every `stg_powerschool__students` column
  plus the Focus branch, with `_dbt_source_relation` and `_dbt_source_project`
  intact.

- [ ] **Step 1: Write the union model**

Two things are load-bearing here.

`source_column_name=none` — without it the macro emits its own
`_dbt_source_relation` naming the kipptaf relation, which collides with the
pass-through column and breaks `extract_region`.

**Anti-join, not a blanket archive exclusion.** Verified against prod: the Miami
archive holds 3,946 students, and 493 of them are absent from Focus. Focus was
seeded with the active population, not the full history. Dropping the archive
branch wholesale would silently remove those 493 from `dim_students`. They are
all departed (zero currently enrolled, zero graduated — 453 transferred out) and
carry no enrollment rows, so nothing breaks, but a −492-row change to a
Cube-facing dimension is churn nobody asked for. Keep them.

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_powerschool__students"),
                    ref("int_focus__students_conformed"),
                ],
                source_column_name=none,
            )
        }}
    ),

    focus_students as (
        select student_number,
        from {{ ref("int_focus__students_conformed") }}
    )

-- Focus supersedes the frozen archive for every Miami student it carries, so an
-- archive row for such a student would double-count. The archive still holds 493
-- departed students Focus never received; those stay, or dim_students loses them.
-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select u.*,
from union_relations as u
left join focus_students as f on u.student_number = f.student_number
where
    u._dbt_source_project != 'kippmiami'
    or u._dbt_source_relation like '%\\_focus%'
    or f.student_number is null
```

- [ ] **Step 2: Prove the double-count filter works before repointing anything**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_students__students \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Then query the dev relation. Expected: zero duplicate Miami student numbers.

```sql
select _dbt_source_project, student_number, count(*) as n
from `teamster-332318.zz_cbini_kipptaf.int_students__students`
group by _dbt_source_project, student_number
having count(*) > 1
```

Expected: 0 rows.

Then confirm the anti-join kept the archive-only students rather than dropping
them — this is the whole point of the anti-join and a plain duplicate check will
not catch its absence:

```sql
select
    countif(_dbt_source_relation like '%\\_focus%') as from_focus,
    countif(_dbt_source_relation not like '%\\_focus%') as from_archive,
    count(*) as miami_total,
from `teamster-332318.zz_cbini_kipptaf.int_students__students`
where _dbt_source_project = 'kippmiami'
```

Expected (measured in Task 3): `from_focus` 3,955, `from_archive` **492**,
`miami_total` 4,447 — against the 3,945 Miami rows prod carries today. A
`from_archive` of 0 means the anti-join collapsed to a blanket exclusion.

The 492 here versus 493 archive-only students is not drift. The district table
`kippmiami_powerschool.stg_powerschool__students` holds 3,946 rows; the kipptaf
view filters `where dcid >= 1`, dropping the one documented
`dcid = -100, student_number = 0` phantom placeholder. Everything downstream
reads the kipptaf view, so 492 is the number to expect.

Note the doubled backslash in the `LIKE` patterns above. BigQuery rejects `\_`
in a string literal outright (`Illegal escape sequence: \_`), so escaping the
underscore needs `\\_`. This bit Task 3 and applies to every reuse of this
pattern in Tasks 4, 5, and 6.

Add the coverage test as a singular test at
`src/dbt/kipptaf/tests/test_miami_students_spine_covers_archive.sql`:

```sql
-- Every student the frozen archive knows must survive into the spine, via the
-- Focus branch for those Focus carries and the archive branch for the 493 it
-- never received. A miss means the anti-join dropped a student from
-- dim_students; a duplicate means both branches kept the same one.
{{ config(severity="error") }}

with
    archive as (
        select student_number,
        from {{ ref("stg_powerschool__students") }}
        where _dbt_source_project = 'kippmiami'
    ),

    spine as (
        select
            student_number,

            count(*) as spine_rows,
        from {{ ref("int_students__students") }}
        where _dbt_source_project = 'kippmiami'
        group by student_number
    )

select
    a.student_number,

    coalesce(s.spine_rows, 0) as spine_rows,
from archive as a
left join spine as s on a.student_number = s.student_number
where s.spine_rows is distinct from 1
```

- [ ] **Step 3: Prove NJ output is unchanged**

This is the parity guarantee. Compare the new model against prod
`stg_powerschool__students` for the three NJ regions.

```sql
with new as (
    select _dbt_source_project, count(*) as n
    from `teamster-332318.zz_cbini_kipptaf.int_students__students`
    where _dbt_source_project != 'kippmiami'
    group by _dbt_source_project
),
old as (
    select _dbt_source_project, count(*) as n
    from `teamster-332318.kipptaf_powerschool.stg_powerschool__students`
    where _dbt_source_project != 'kippmiami'
    group by _dbt_source_project
)
select
    coalesce(new._dbt_source_project, old._dbt_source_project) as project,
    new.n as new_rows,
    old.n as old_rows,
from new
full join old on new._dbt_source_project = old._dbt_source_project
```

Expected: `new_rows` equals `old_rows` for every NJ project.

- [ ] **Step 4: Add the properties file**

```yaml
models:
  - name: int_students__students
    description: >-
      SIS-agnostic student spine. Unions the PowerSchool student staging view
      for the three New Jersey regions with the conformed Focus branch for
      Miami. The Miami PowerSchool archive is excluded, because Focus now
      carries Miami identity and including both double-counts every returning
      student.
    config:
      meta:
        contains_pii: true
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_number
              - _dbt_source_project
    columns:
      - name: student_number
        description: Canonical network student number.
      - name: _dbt_source_project
        description:
          District code location, passed through from the source union view.
      - name: _dbt_source_relation
        description: Source relation, passed through from the source union view.
```

- [ ] **Step 5: Repoint `dim_students`**

One-line change at `dim_students.sql:5`:

```sql
        from {{ ref("int_students__students") }} as s
```

- [ ] **Step 6: Build the mart and prove `student_key` stability**

This is the no-churn guarantee and must be proven, not assumed.

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_students__students dim_students \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

```sql
select count(*) as miami_keys_that_moved
from `teamster-332318.kipptaf_marts.dim_students` as p
inner join
    `teamster-332318.zz_cbini_kipptaf_marts.dim_students` as n
    on p.lea_student_identifier = n.lea_student_identifier
where p._dbt_source_project = 'kippmiami' and p.student_key != n.student_key
```

Expected: 0. A non-zero result means Miami history detached from its keys — stop
and diagnose before continuing.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
~/.cache/trunk/launcher/trunk check --force --no-fix \
  src/dbt/kipptaf/models/students/intermediate/int_students__students.sql \
  src/dbt/kipptaf/models/students/intermediate/properties/int_students__students.yml \
  src/dbt/kipptaf/models/marts/dimensions/dim_students.sql </dev/null
```

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/students/ src/dbt/kipptaf/models/marts/dimensions/dim_students.sql
git -C "$wt" commit -m "feat(dbt): add the SIS-agnostic student spine and repoint dim_students

Refs #4731"
```

---

### Task 4: `int_focus__student_user_fields_conformed` and `int_students__student_user_fields`

`dim_students` reads `stg_powerschool__u_studentsuserfields` for `fleid` and
`gifted_and_talented`. Focus supplies FLEID as `florida_education_identifier`;
gifted lives on the Focus `Gifted (Computed)` custom field, which Task 2's
investigation found effectively unpopulated.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_user_fields_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_user_fields_conformed.yml`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__student_user_fields.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_user_fields.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_students.sql:72-74`

**Interfaces:**

- Consumes: `ref("int_focus__students_conformed")` from Task 2.
- Produces: `int_students__student_user_fields`, carrying `student_number`,
  `fleid`, `gifted_and_talented`, `_dbt_source_relation`, `_dbt_source_project`.
  No DCID.

- [ ] **Step 1: Confirm the archive's `gifted_and_talented` domain**

```sql
select gifted_and_talented, count(*) as students
from `teamster-332318.kippmiami_powerschool.stg_powerschool__u_studentsuserfields`
group by gifted_and_talented
order by students desc
```

Record the domain. `dim_students.sql:47` coalesces it to `'N'`, so a null from
Focus reads as not-gifted — acceptable here, unlike the IEP case, because `'N'`
is the archive's own default rather than a fabricated negative.

- [ ] **Step 2: Write the conform model**

Keyed on `student_number`, not a DCID. `gifted_and_talented` gets the same
archive carry-forward treatment as the three status fields: Focus's
`Gifted (Computed)` custom field is log-based and effectively unpopulated.

```sql
with
    -- The archive's user fields are keyed on studentsdcid, so resolve to
    -- student_number here. dcid is PowerSchool plumbing and stops at this
    -- layer; the mart joins on student_number.
    archive as (
        select
            s.student_number,
            suf.gifted_and_talented,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on s.dcid = suf.studentsdcid
            and s._dbt_source_project = suf._dbt_source_project
        where s._dbt_source_project = 'kippmiami'
    )

select
    c._dbt_source_relation,
    c._dbt_source_project,
    c.student_number,

    a.gifted_and_talented,

    c.florida_education_identifier as fleid,
from {{ ref("int_focus__students_conformed") }} as c
left join archive as a on c.student_number = a.student_number
```

- [ ] **Step 3: Write the union model, resolving the PowerSchool branch to
      `student_number`**

The PowerSchool staging model carries only `studentsdcid`, so the union cannot
be a bare passthrough — the branch resolves to `student_number` first. This is
the translation that lets the mart stop joining on `dcid`.

```sql
with
    powerschool as (
        select
            suf.* except (studentsdcid),

            s.student_number,
        from {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on suf.studentsdcid = s.dcid
            and suf._dbt_source_project = s._dbt_source_project
        -- Miami's archive is superseded by the Focus branch below.
        where s._dbt_source_project != 'kippmiami'
    ),

    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("int_focus__student_user_fields_conformed"),
                ],
                source_column_name=none,
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from powerschool

union all

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from union_relations
```

If the two branches' column sets differ, replace the hand-written `UNION ALL`
with a single `union_relations` over both a materialized `powerschool` CTE and
the conform model, which restores the automatic null-fill. Prefer that if there
is any doubt.

- [ ] **Step 4: Repoint `dim_students` and change its join key**

At `dim_students.sql:72-74`, both the ref and the join key change. This is the
edit that removes `dcid` from the mart:

```sql
left join
    {{ ref("int_students__student_user_fields") }} as suf
    on s.student_number = suf.student_number
    and s._dbt_source_project = suf._dbt_source_project
```

Leave the `stg_powerschool__s_nj_stu_x` join at `dim_students.sql:76-78`
untouched. It is NJ-only, so a null Miami `dcid` correctly matches nothing.

- [ ] **Step 5: Build and prove Miami students now resolve their FLEID**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__student_user_fields_conformed int_students__student_user_fields dim_students \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

```sql
select
    countif(state_student_identifier is not null) as with_fleid,
    count(*) as miami_students,
from `teamster-332318.zz_cbini_kipptaf_marts.dim_students`
where _dbt_source_project = 'kippmiami'
```

Expected: `with_fleid` is a large majority of `miami_students`. A `with_fleid`
of 0 means the `student_number` join is not resolving.

Also confirm NJ did not regress. The PowerSchool branch gained an inner join to
`stg_powerschool__students` to resolve `studentsdcid`, which silently drops any
user-field row whose DCID has no matching student:

```sql
select
    (
        select count(*)
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__u_studentsuserfields`
        where _dbt_source_project != 'kippmiami'
    ) as staging_nj_rows,
    (
        select count(*)
        from `teamster-332318.zz_cbini_kipptaf.int_students__student_user_fields`
        where _dbt_source_project != 'kippmiami'
    ) as spine_nj_rows
```

Expected: equal. A shortfall means orphaned `studentsdcid` values — switch the
inner join to a left join so the row survives with a null `student_number`,
rather than silently dropping NJ data to satisfy a Miami change.

- [ ] **Step 6: Write both properties files, lint, and commit**

Both need a model `description:`, per-column `description:`, and a uniqueness
test on `student_number` plus `_dbt_source_project`. Set
`config: meta: contains_pii: true` on both — FLEID is a state student
identifier.

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/ src/dbt/kipptaf/models/students/ src/dbt/kipptaf/models/marts/dimensions/dim_students.sql
git -C "$wt" commit -m "feat(dbt): conform Focus student user fields into the spine

Refs #4731"
```

---

### Task 5: `int_students__student_core_fields` and the two status dimensions

`dim_student_ell_status` and `dim_student_iep_status` both read
`stg_powerschool__studentcorefields`, joined on `students_dcid`. This is the
task that retires that join, and where the status carry-forward becomes visible
in a mart.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_core_fields_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_core_fields_conformed.yml`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__student_core_fields.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__student_core_fields.yml`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_ell_status.sql:107`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_iep_status.sql:155`

**Interfaces:**

- Consumes: `ref("int_focus__students_conformed")` from Task 2.
- Produces: `int_students__student_core_fields`, carrying `student_number`,
  `lep_status BOOL`, `spedlep STRING`, `_dbt_source_relation`,
  `_dbt_source_project`. No DCID.

- [ ] **Step 1: Write the conform model**

The carry-forward happens HERE, not on the student spine. Task 2 established
that the archive keeps `spedlep` and `lep_status` on `studentcorefields`, not on
its students table, so each conform model carries forward from its own archive
counterpart. `int_focus__students_conformed` does NOT project these two columns
— do not try to read them from it.

```sql
with
    -- Neither field has a usable Focus source. Focus ese_fefp_code is an FEFP
    -- funding code covering 162 of 419 archive SPED students, and
    -- english_language_learner_pk_12 puts 98% of students at the
    -- not-applicable code. Carry the archive value forward for returning
    -- students; new students get null, because a false negative on IEP status
    -- is compliance-adjacent and unknown must read as unknown.
    --
    -- The archive keys these on studentsdcid, so resolve to student_number
    -- here. dcid is PowerSchool plumbing and stops at this layer.
    archive as (
        select
            s.student_number,

            scf.spedlep,
            scf.lep_status,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
            and s._dbt_source_project = scf._dbt_source_project
        where s._dbt_source_project = 'kippmiami'
    )

select
    c._dbt_source_relation,
    c._dbt_source_project,
    c.student_number,

    a.spedlep,
    a.lep_status,
from {{ ref("int_focus__students_conformed") }} as c
left join archive as a on c.student_number = a.student_number
```

Both columns get a warn-severity `not_null` test in the properties file, so the
gap stays visible and closes when Focus is populated.

- [ ] **Step 2: Write the union model, resolving the PowerSchool branch to
      `student_number`**

Same shape as Task 4 — the staging model carries only `studentsdcid`, so the
PowerSchool branch resolves it here rather than pushing `dcid` into the marts.

```sql
with
    powerschool as (
        select
            scf.* except (studentsdcid),

            s.student_number,
        from {{ ref("stg_powerschool__studentcorefields") }} as scf
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on scf.studentsdcid = s.dcid
            and scf._dbt_source_project = s._dbt_source_project
        -- Miami's archive is superseded by the Focus branch below.
        where s._dbt_source_project != 'kippmiami'
    ),

    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("int_focus__student_core_fields_conformed"),
                ],
                source_column_name=none,
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from powerschool

union all

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from union_relations
```

- [ ] **Step 3: Repoint both marts and change their join keys**

Both `pm_leg` CTEs join enrollment to core fields on `students_dcid`. Change the
ref and the key together — this is what removes `dcid` from these two marts.

`dim_student_ell_status.sql:106-109`:

```sql
        inner join
            {{ ref("int_students__student_core_fields") }} as scf
            on e.student_number = scf.student_number
            and e._dbt_source_project = scf._dbt_source_project
```

`dim_student_iep_status.sql:154-157`:

```sql
        left join
            {{ ref("int_students__student_core_fields") }} as scf
            on e.student_number = scf.student_number
            and e._dbt_source_project = scf._dbt_source_project
```

Keep each join's existing type — `inner` for ELL, `left` for IEP. Swapping one
changes which students appear in the dim.

Leave the two `stg_powerschool__s_nj_stu_x` joins in
`dim_student_ell_status.sql` (`nj_primary`, `nj_secondary`) on `students_dcid`.
They are NJ-only, and Miami correctly matches nothing there.

**Paterson is in scope for this change.** The IEP `pm_leg` filters
`_dbt_source_project in ('kipppaterson', 'kippmiami')`, so the join-key swap
affects Paterson too. Step 4 must check Paterson parity, not just NJ as a whole.

Paterson is expected to move onto the NJ edplan path (`nj_leg`) like Newark and
Camden, which would take it off `pm_leg` entirely. That cannot happen yet —
`int_edplan__njsmart_powerschool_union` carries zero Paterson rows and no
`kipppaterson_edplan` source exists — so leave the filter as it is. This task's
change is a join-key swap that keeps Paterson correct in the meantime and does
not entrench its PowerSchool path; when the edplan migration lands, Paterson
drops out of `pm_leg` and the swap becomes Miami-only for free.

Note the asymmetry so it does not read as an oversight: the ELL `pm_leg` is
already Miami-only, because `stg_powerschool__s_nj_stu_x` carries Paterson and
`nj_leg` covers it. Only IEP still routes Paterson through PowerSchool.

- [ ] **Step 4: Build and confirm Miami rows appear where they were zero**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__student_core_fields_conformed int_students__student_core_fields \
    dim_student_ell_status dim_student_iep_status \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Miami rows in these two dims depend on Task 8's enrollment branch, so at this
point confirm only that the existing regions are unchanged and the join
resolves. Paterson is the one to watch — its IEP rows flow through the same
`pm_leg` whose join key just changed:

```sql
select _dbt_source_project, count(*) as n
from `teamster-332318.zz_cbini_kipptaf_marts.dim_student_iep_status`
group by _dbt_source_project
```

Expected: every non-Miami count, **including `kipppaterson`**, matches the same
query against `teamster-332318.kipptaf_marts.dim_student_iep_status`. A Paterson
delta means the `studentsdcid`-to-`student_number` resolution lost or fanned out
rows — fix it before proceeding, because that is a regression in a region this
issue was not meant to touch.

Miami may still be 0 until Task 8 lands; that is correct at this point and is
re-checked in Task 11.

- [ ] **Step 5: Write both properties files, lint, and commit**

Both get a uniqueness test on `student_number` plus `_dbt_source_project`, a
model `description:`, and per-column descriptions naming the carry-forward.

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/ src/dbt/kipptaf/models/students/ src/dbt/kipptaf/models/marts/dimensions/
git -C "$wt" commit -m "feat(dbt): conform Focus student core fields into the spine

Refs #4731"
```

---

### Task 6: `int_students__schools` and its five mart consumers

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__schools_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__schools_conformed.yml`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/int_students__schools.sql`
- Create:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__schools.yml`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_assessment_goals.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_course_sections.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_school_calendars.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_student_enrollments.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql`

**Interfaces:**

- Consumes: `ref("int_focus__schools")` (existing wrapper),
  `ref("stg_google_sheets__people__locations")`.
- Produces: `int_students__schools`, carrying `school_number`, `name`,
  `abbreviation`, `location_key`, `_dbt_source_relation`, `_dbt_source_project`.

- [ ] **Step 1: Read what the five marts actually consume**

Column needs differ per mart, and the conform model must supply the union of
them. Do not guess:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf/models/marts/dimensions
grep -n -A6 'stg_powerschool__schools' \
  dim_assessment_goals.sql dim_course_sections.sql dim_school_calendars.sql \
  dim_student_enrollments.sql dim_terms.sql
```

Record every referenced column. The conform model in Step 2 must project all of
them.

- [ ] **Step 2: Write the conform model**

`stg_powerschool__schools` joins the locations sheet on `powerschool_school_id`;
the Focus equivalent joins on `focus_school_id`, the same key
`int_focus__student_enrollments` already uses.

```sql
select
    s._dbt_source_relation,
    s._dbt_source_project,
    s.school_number,
    s.school_title as name,

    loc.location_key,
    loc.abbreviation,
from {{ ref("int_focus__schools") }} as s
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on s.school_number = loc.focus_school_id
```

Extend the projection with any additional column Step 1 found.

- [ ] **Step 3: Write the union model**

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_powerschool__schools"),
                    ref("int_focus__schools_conformed"),
                ],
                source_column_name=none,
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from union_relations
where
    _dbt_source_project != 'kippmiami'
    or _dbt_source_relation like '%\\_focus%'
```

**First check whether schools need the anti-join too.** Task 3 found the student
archive holds 492 students Focus never received. Schools can have the same shape
— a closed or renamed Miami school the archive knows and Focus does not. A
missing school row null-fills school attributes on every historical enrollment
that references it. Measure before choosing:

```sql
select count(*) as archive_only_schools
from `teamster-332318.kipptaf_powerschool.stg_powerschool__schools` as a
left join `teamster-332318.kipptaf_focus.int_focus__schools` as f
    on a.school_number = f.school_number
where a._dbt_source_project = 'kippmiami' and f.school_number is null
```

If that returns 0, the blanket filter above is correct as written. If it returns
more than 0, switch to the anti-join shape from Task 3 Step 1 so those schools
survive, and say which you did in the commit message.

- [ ] **Step 4: Repoint the five marts**

One `ref()` swap each, `stg_powerschool__schools` to `int_students__schools`.
Join keys are unchanged in all five.

- [ ] **Step 5: Build the five marts and check NJ parity plus Miami presence**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__schools_conformed int_students__schools \
    dim_assessment_goals dim_course_sections dim_school_calendars \
    dim_student_enrollments dim_terms \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

For each of the five, compare NJ row counts against the prod mart. Expected:
identical. Any delta is a regression, not an improvement — investigate before
proceeding.

- [ ] **Step 6: Write both properties files, lint, and commit**

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/ src/dbt/kipptaf/models/students/ src/dbt/kipptaf/models/marts/dimensions/
git -C "$wt" commit -m "feat(dbt): add the SIS-agnostic school spine and repoint its five marts

Refs #4731"
```

---

### Task 7: `int_focus__student_enrollment_conformed`

The single highest-leverage model. Its consumer serves 13 marts.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__student_enrollment_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__student_enrollment_conformed.yml`

**Interfaces:**

- Consumes: `ref("int_focus__student_enrollments")` (existing wrapper — note the
  kipptaf model is plural while the underlying source is singular
  `int_focus__student_enrollment`), `ref("int_focus__students_conformed")`.
- Produces: a relation matching the `int_powerschool__student_enrollment_union`
  column vocabulary: `student_number`, `academic_year`, `entrydate`, `exitdate`,
  `enroll_status`, `grade_level`, `schoolid`, `rn_year`, `year_in_school`,
  `year_in_network`. No DCID. Task 8 consumes it.

- [ ] **Step 1: Read both column sets side by side**

The conform model's job is to make one match the other. Read them, do not infer:

```sql
select 'focus' as src, column_name, data_type
from `teamster-332318.kippmiami_focus.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'int_focus__student_enrollment'
union all
select 'network', column_name, data_type
from `teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'int_powerschool__student_enrollment_union'
order by src, column_name
```

- [ ] **Step 2: Note the misnamed upstream column before using it**

`int_focus__student_enrollment.student_number` holds the **prefixed** Focus id,
not the network student number. Joining on it by name returns zero matches with
no error. The conform model must unprefix it exactly as Task 2 did, and must not
pass the upstream column through under its own name.

- [ ] **Step 3: Write the conform model**

```sql
with
    identified as (
        select
            *,

            -- Upstream column is misnamed: it holds the prefixed Focus id, not
            -- the network student number. Unprefix with the same rule Task 2
            -- applied to the student spine.
            cast(
                regexp_replace(cast(student_number as string), r'^8400', '') as int64
            ) as network_student_number,
        from {{ ref("int_focus__student_enrollments") }}
    )

select
    i._dbt_source_relation,
    i._dbt_source_project,
    i.academic_year,
    i.entrydate,
    i.exitdate,
    i.enroll_status,
    i.grade_level,
    i.rn_year,
    i.year_in_school,
    i.year_in_network,

    i.network_student_number as student_number,

    i.ps_schoolid as schoolid,

    -- No students_dcid. Task 5 moved the enrollment-to-core-field joins in
    -- dim_student_ell_status and dim_student_iep_status onto student_number,
    -- so it null-fills for Miami and the NJ-only s_nj_stu_x joins that still
    -- use it correctly match nothing.
from identified as i
```

Adjust the projection to whatever Step 1 showed. Any network column Focus cannot
supply is simply omitted — `union_relations` null-fills it in Task 8.

- [ ] **Step 4: Build and reconcile against the archive's real stints**

Focus covers AY2018 through AY2026, so the conformed output must match the
archive's real stints once alumni placeholders are excluded.

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__student_enrollment_conformed \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

```sql
with conformed as (
    select student_number, academic_year, entrydate
    from `teamster-332318.zz_cbini_kipptaf.int_focus__student_enrollment_conformed`
    where academic_year between 2018 and 2025
),
archive as (
    select student_number, academic_year, entrydate
    from `teamster-332318.kipptaf_powerschool.int_powerschool__student_enrollment_union`
    where
        _dbt_source_project = 'kippmiami'
        and academic_year between 2018 and 2025
        and entrydate is not null
)
select
    (select count(*) from conformed) as conformed_stints,
    (select count(*) from archive) as archive_stints,
    (select count(*) from conformed
     except distinct
     select count(*) from archive) as shape_differs
```

Then diff the sets directly:

```sql
select 'in_focus_only' as side, count(*) as n
from (
    select student_number, academic_year, entrydate
    from `teamster-332318.zz_cbini_kipptaf.int_focus__student_enrollment_conformed`
    where academic_year between 2018 and 2025
    except distinct
    select student_number, academic_year, entrydate
    from `teamster-332318.kipptaf_powerschool.int_powerschool__student_enrollment_union`
    where _dbt_source_project = 'kippmiami' and academic_year between 2018 and 2025
      and entrydate is not null
)
```

Expected: small and explainable. A large asymmetry means the unprefix or the
date mapping is wrong. Record the number in the PR either way.

- [ ] **Step 5: Write the properties file, lint, and commit**

Uniqueness test on the combination `student_number`, `academic_year`,
`entrydate`. Set `config: meta: contains_pii: true`.

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/
git -C "$wt" commit -m "feat(dbt): conform Focus enrollment stints to the network vocabulary

Refs #4731"
```

---

### Task 8: Add the Focus branch to `int_powerschool__student_enrollment_union`

The only model in this plan that keeps the Miami archive. It holds the 1,002
alumni graduate placeholders that `kipptaf/CLAUDE.md` requires retaining for
KIPP Forward reporting, and Focus has no equivalent.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__student_enrollment_union.sql`
- Create: `src/dbt/kipptaf/tests/test_miami_enrollment_branches_disjoint.sql`

**Interfaces:**

- Consumes: `ref("int_focus__student_enrollment_conformed")` from Task 7.
- Produces: the existing model, now Miami-populated for AY2026.

- [ ] **Step 1: Write the failing disjointness test first**

```sql
-- Miami's enrollment comes from two branches: Focus for real stints, and the
-- frozen archive for alumni graduate placeholders only. A student-year-entry
-- appearing in both means the placeholder filter is wrong and the student is
-- double-counted.
select
    student_number,
    academic_year,
    entrydate,
    count(*) as branches,
from {{ ref("int_powerschool__student_enrollment_union") }}
where _dbt_source_project = 'kippmiami'
group by student_number, academic_year, entrydate
having count(*) > 1
```

- [ ] **Step 2: Modify the union**

The archive filter goes in the model body, not `union_relations`' `where`
argument — that argument applies to every relation, which would strip the NJ
regions' real stints.

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__student_enrollment_union",
                    ),
                ]
            )
        }}
    ),

    with_project as (
        select
            *,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,
        from unioned
    ),

    -- Miami's SIS moved to Focus, so the archive contributes exactly one thing:
    -- the alumni graduate placeholders (enroll_status 3, null entry and exit,
    -- one row per academic year) that KIPP Forward reporting needs and Focus
    -- has no equivalent for. Its real stints come from Focus instead.
    powerschool_branch as (
        select *,
        from with_project
        where
            _dbt_source_project != 'kippmiami'
            or (enroll_status = 3 and entrydate is null)
    )

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select *,
from powerschool_branch

union all

-- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
select
    *,
    'kippmiami' as _dbt_source_project,
    'Miami' as region,
from {{ ref("int_focus__student_enrollment_conformed") }}
```

The two `UNION ALL` branches must project identical column sets. If they do not,
wrap the Focus branch in a second `union_relations` against the PowerSchool
branch instead of a hand-written `UNION ALL`, which restores the automatic
null-fill.

- [ ] **Step 3: Build and run the disjointness test**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_powerschool__student_enrollment_union \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: PASS on the disjointness test.

- [ ] **Step 4: Prove the alumni placeholders survived**

```sql
select count(*) as placeholders
from `teamster-332318.zz_cbini_kipptaf_powerschool.int_powerschool__student_enrollment_union`
where _dbt_source_project = 'kippmiami' and enroll_status = 3 and entrydate is null
```

Expected: 1,002 — the same count prod carries today. A lower number means the
filter dropped rows KIPP Forward depends on.

- [ ] **Step 5: Prove NJ parity**

```sql
select _dbt_source_project, count(*) as n
from `teamster-332318.zz_cbini_kipptaf_powerschool.int_powerschool__student_enrollment_union`
where _dbt_source_project != 'kippmiami'
group by _dbt_source_project
```

Expected: identical to the same query against
`teamster-332318.kipptaf_powerschool.int_powerschool__student_enrollment_union`.

- [ ] **Step 6: Prove Miami AY2026 is no longer zero**

This is the headline result of the whole issue.

```sql
select academic_year, count(*) as rows_
from `teamster-332318.zz_cbini_kipptaf_powerschool.int_powerschool__student_enrollment_union`
where _dbt_source_project = 'kippmiami' and academic_year = 2026
group by academic_year
```

Expected: roughly 1,585, the Focus AY2026 enrollment row count. Prod is 0 today.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/powerschool/ src/dbt/kipptaf/tests/
git -C "$wt" commit -m "feat(dbt): restore Miami enrollment via the Focus branch

Refs #4731"
```

---

### Task 9: Terms

`int_powerschool__terms` and `stg_powerschool__terms` both need a Focus branch,
sourced from `stg_focus__marking_periods`.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__terms_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__terms_conformed.yml`
- Modify: `src/dbt/kipptaf/models/focus/sources-kippmiami.yml`
- Create: `src/dbt/kipptaf/models/focus/staging/stg_focus__marking_periods.sql`
- Create:
  `src/dbt/kipptaf/models/focus/staging/properties/stg_focus__marking_periods.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__terms.sql`

**Interfaces:**

- Consumes: `source("kippmiami_focus", "stg_focus__marking_periods")`.
- Produces: `int_focus__terms_conformed`, matching the PowerSchool terms
  vocabulary.

- [ ] **Step 1: Declare and wrap `stg_focus__marking_periods`**

Same pattern as Task 1 — a source entry in `sources-kippmiami.yml` plus a
`union_relations` passthrough. Marking periods are not PII, so no `contains_pii`
tag.

- [ ] **Step 2: Read both column sets**

```sql
select 'focus' as src, column_name, data_type
from `teamster-332318.kippmiami_focus.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'stg_focus__marking_periods'
union all
select 'network', column_name, data_type
from `teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'int_powerschool__terms'
order by src, column_name
```

- [ ] **Step 3: Write the conform model**

Project the network vocabulary — term id, name, abbreviation, school number,
year id, start and end dates — from the Focus marking-period columns Step 2
identified. Omit anything Focus cannot supply; `union_relations` null-fills.

- [ ] **Step 4: Add the Focus branch to both terms models**

Both take the branch in place, following the Task 8 shape: keep the four
PowerSchool sources, exclude the Miami archive, union the conform model.

- [ ] **Step 5: Build, check NJ parity, and confirm Miami terms appear**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select stg_focus__marking_periods int_focus__terms_conformed \
    stg_powerschool__terms int_powerschool__terms \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: NJ counts identical to prod, Miami AY2026 terms non-zero.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/ src/dbt/kipptaf/models/powerschool/
git -C "$wt" commit -m "feat(dbt): restore Miami terms via the Focus marking periods

Refs #4731"
```

---

### Task 10: `int_powerschool__teacher_grade_levels`

Seventeen marts downstream, the widest reach in the plan. Depends on all three
prerequisite models from Task 1.

**Files:**

- Create:
  `src/dbt/kipptaf/models/focus/intermediate/int_focus__teacher_grade_levels_conformed.sql`
- Create:
  `src/dbt/kipptaf/models/focus/intermediate/properties/int_focus__teacher_grade_levels_conformed.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__teacher_grade_levels.sql`

**Interfaces:**

- Consumes: `ref("int_focus__schedule")`, `ref("int_focus__users")`,
  `ref("stg_focus__co_teachers")` — all from Task 1 or already present.
- Produces: `int_focus__teacher_grade_levels_conformed`, matching the network
  teacher-grade-level vocabulary.

- [ ] **Step 1: Read the network model's column set and the Focus inputs**

```sql
select 'network' as src, column_name, data_type
from `teamster-332318.kipptaf_powerschool.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'int_powerschool__teacher_grade_levels'
union all
select table_name, column_name, data_type
from `teamster-332318.kippmiami_focus.INFORMATION_SCHEMA.COLUMNS`
where table_name in ('int_focus__schedule', 'int_focus__users', 'stg_focus__co_teachers')
order by src, column_name
```

- [ ] **Step 2: Write the conform model**

Join schedule to users for the primary teacher and to co-teachers for the
secondary, projecting the network vocabulary Step 1 identified. Grade levels
come from the schedule's course-period grade level.

- [ ] **Step 3: Add the Focus branch to the network model**

Same shape as Task 8 — four PowerSchool sources, Miami archive excluded, conform
model unioned.

- [ ] **Step 4: Build and verify**

```bash
cd /workspaces/teamster
uv run dbt build \
  --select int_focus__teacher_grade_levels_conformed int_powerschool__teacher_grade_levels \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: NJ counts identical to prod, Miami teachers present for AY2026.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" add src/dbt/kipptaf/models/focus/ src/dbt/kipptaf/models/powerschool/
git -C "$wt" commit -m "feat(dbt): restore Miami teacher grade levels via Focus

Refs #4731"
```

---

### Task 11: Whole-graph validation and PR

Nothing here changes model code. It runs the spec's six validation gates across
the finished branch and writes the results into the PR.

**Files:**

- Create: `.claude/scratch/4731-validation.md` (local only — holds PII-adjacent
  counts during the run, never pushed)

- [ ] **Step 1: Resolve every downstream consumer**

`--empty` proves column resolution across the whole descendant graph without
moving data.

```bash
cd /workspaces/teamster
uv run dbt build --empty \
  --select int_students__students+ int_students__schools+ \
    int_students__student_core_fields+ int_students__student_user_fields+ \
    int_powerschool__student_enrollment_union+ int_powerschool__terms+ \
    int_powerschool__teacher_grade_levels+ \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --favor-state \
  --project-dir .worktrees/cbini/feat/claude-focus-identity-spine/src/dbt/kipptaf
```

Expected: PASS. Any failure is an unrepointed consumer or a column the conform
models failed to supply.

- [ ] **Step 2: NJ parity across every modified model**

For each of the seven modified models, run the count plus null-safe distinct-key
comparison. `concat()` returns NULL when any argument is NULL and silently
miscounts, so use `format()`:

```sql
select
    count(*) as rows_,
    count(distinct format('%T|%T', student_number, academic_year)) as distinct_keys,
from `teamster-332318.<schema>.<model>`
where _dbt_source_project != 'kippmiami'
```

Expected: identical between the dev build and prod, for every model. Record each
pair in `.claude/scratch/4731-validation.md`.

- [ ] **Step 3: `student_key` stability across the full Miami population**

```sql
select count(*) as keys_that_moved
from `teamster-332318.kipptaf_marts.dim_students` as p
inner join
    `teamster-332318.zz_cbini_kipptaf_marts.dim_students` as n
    on p.lea_student_identifier = n.lea_student_identifier
where p._dbt_source_project = 'kippmiami' and p.student_key != n.student_key
```

Expected: 0.

- [ ] **Step 4: Confirm the eight fully-restored marts carry Miami rows**

`dim_students`, `dim_student_enrollments`, `dim_student_enrollment_status`,
`dim_student_ell_status`, `dim_student_iep_status`,
`dim_student_meal_eligibility_status`, `fct_behavioral_consequences`,
`fct_family_communications`. Build each and count Miami AY2026 rows. Expected:
non-zero for all eight. A zero in one of the three status dims means a
`student_number` join is not resolving — that is the failure mode this plan was
written around, and it is silent.

Also confirm no `dcid` survived into a mart SELECT, which the rubric forbids:

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
grep -rn 'dcid' src/dbt/kipptaf/models/marts/
```

Expected: no hits outside `fct_grades_assignments`, which is out of scope for
this issue and tracked for Phase 5.

- [ ] **Step 5: Measure the bridge-orphan improvement**

Restoring Miami students to `dim_students` fixes a pre-existing FK gap nobody
filed. `bridge_student_contacts.student_key` has a `relationships` test to
`dim_students.student_key`; prod carries roughly 2,077 orphans, and a Task 4 dev
build showed 23. The direction matters — adding rows to the parent dimension can
only reduce orphans, never create them, so any residual is pre-existing and any
drop is this branch's doing.

```sql
select count(*) as orphans
from `teamster-332318.kipptaf_marts.bridge_student_contacts` as b
left join `teamster-332318.kipptaf_marts.dim_students` as d
    on b.student_key = d.student_key
where d.student_key is null
```

Run the same against the dev-built pair and put both numbers in the PR. If the
dev number is HIGHER than prod, something in the spine dropped students — stop
and diagnose.

- [ ] **Step 6: Record the known-null status counts**

The three status dims carry null values for students new since the freeze. Count
them so the PR states the number rather than implying full restoration:

```sql
select
    countif(spedlep is null) as null_iep,
    countif(lunchstatus is null) as null_meal,
    countif(lep_status is null) as null_ell,
    count(*) as miami_students,
from `teamster-332318.zz_cbini_kipptaf.int_focus__students_conformed`
```

- [ ] **Step 7: Refresh the staging copies so CI can read them**

kipptaf `sources-kipp*` resolve to `zz_stg_*` for `target=staging`, and a
district prod merge does not refresh them. Without this, CI reads a stale copy
and fails deterministically. This recreates shared tables, so it needs direct
user authorization — hand it over rather than running it unprompted:

```bash
uv run dbt clone --target staging \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod \
  --project-dir /workspaces/teamster/src/dbt/kippmiami
```

- [ ] **Step 8: Full-branch lint**

A `--force` check over this many files takes more than two minutes and its
spinner emits no result lines, so grepping interim output reads as a false
clean. Background it and only interpret the output after it exits.

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
~/.cache/trunk/launcher/trunk check --force --no-fix \
  $(git -C . diff --name-only origin/main...HEAD | grep -E '\.(sql|yml|md)$' | while read f; do [ -f "$f" ] && echo "$f"; done) </dev/null
```

- [ ] **Step 9: Open the PR**

Use `.github/pull_request_template.md` as the body. It must state, because none
of it is obvious from the diff:

- Miami AY2026 goes from 0 to roughly 1,585 enrollment rows.
- Eight marts fully restored; 26 more become resolvable but stay row-empty until
  Phases 2 and 3.
- The three status dimensions carry null for students new since the freeze, with
  the counts from Step 5.
- The 33 non-mart consumers listed in the spec appendix stay PowerSchool-only
  and Miami-less until Phase 5, so a Tableau extract and Cube will disagree for
  Miami during this window. That is expected, not a defect.
- The one AY2026 Focus id lacking the `8400` prefix needs an Ops correction.

```bash
cd /workspaces/teamster
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-focus-identity-spine
git -C "$wt" push -u origin cbini/feat/claude-focus-identity-spine
```

Then create the PR with `mcp__github__create_pull_request`, body referencing
`Closes #4731`.

---

## Follow-ups to file separately, not here

- Rename `int_focus__student_enrollment.student_number` — it holds the prefixed
  id under a name implying the network student number, and its consumers
  (`int_tableau__fresh_enrollment_scaffold`, `rpt_focus__student_enrollment`)
  need checking for the same assumption.
- `src/dbt/CLAUDE.md` describes `union_relations` as producing "the column
  intersection." It produces a superset with null-fill
  (`dbt_utils/macros/sql/union.sql:113`). The wrong description is what makes
  the null-filling design in this plan look impossible.
- Ownership for populating Focus ESE, meal, and ELL fields, which is what closes
  the three status gaps.
- `fct_grades_assignments` still selects and joins on `students_dcid`
  (`fct_grades_assignments.sql:12`, `:51`, `:98`), including it in a surrogate
  key. That is the same R2 and plumbing violation this plan removes from the
  four student dimensions, but it sits in the gradebook vertical, which Phase 3
  covers. Fixing it here would widen the blast radius for no Miami benefit,
  since Miami gradebook data does not exist yet.
