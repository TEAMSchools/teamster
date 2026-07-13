# Vendor Assessments in Enrollment-Scoped Fact — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Every implementer MUST first invoke
> the `Skill` tool with skill `dbt:using-dbt-for-analytics-engineering` before
> touching any dbt file.

**Goal:** Add iReady, STAR/Renaissance, and DIBELS/Amplify scores to
`fct_assessment_scores_enrollment_scoped` (issue
[#3625](https://github.com/TEAMSchools/teamster/issues/3625)), per the approved
spec
`docs/superpowers/specs/2026-07-13-vendor-assessments-enrollment-scoped-fact-design.md`.

**Architecture:** Inline branches (spec Approach A). Each vendor intermediate
gains two additive columns (`_dbt_source_project`, `illuminate_subject`); then
the section resolver, both assessment dims, and the fact each gain vendor
branches mirroring the existing `state_nj`/`state_fl` pattern. iReady and STAR
fact branches dedupe at PK grain (verified upstream duplicates).

**Tech Stack:** dbt (BigQuery), `dbt_utils.generate_surrogate_key`,
`dbt_utils.deduplicate`.

## Global Constraints

- Worktree:
  `/workspaces/teamster/.worktrees/cbini/feat/claude-fct-assessment-scores-vendor-sources`
  (call it `{wt}` below — substitute the full path; use lowercase shell vars).
  ALL file edits target `{wt}/...` paths, never the main checkout.
- Git: `git -C {wt} ...` on every git command. Conventional commits.
- dbt runs:
  `uv run dbt <cmd> --project-dir {wt}/src/dbt/kipptaf --target dev --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod`
  (absolute `--state`; run `uv run dbt deps --project-dir {wt}/src/dbt/kipptaf`
  once first).
- SQL conventions (sqlfluff/CI-enforced; see `src/dbt/CLAUDE.md`): trailing
  commas; no `ORDER BY`/`QUALIFY`/`GROUP BY ALL`; max 1 level of function
  nesting; ST06 column order (plain refs by table, then constants, simple
  functions, nested functions, logicals, case, window); reserved words
  backticked (`` `period` ``); generic tests need `arguments:` nesting.
- `dbt_utils.deduplicate` `order_by` on BigQuery: `desc` OK, no
  `asc nulls last`. Input CTE referenced only by `deduplicate` needs
  `-- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below`.
- Hash values 'iready' / 'star' / 'dibels' (`score_source` = `source_type` =
  `assessment_type`) must be byte-identical across resolver, dims, and fact.
- Dedupe TODOs reference the follow-up issues from Task 1 as `TODO(#NNNN)`.
- Do not run `--target prod` builds or `stage_external_sources` — not needed
  here; all touched models read existing prod/staging relations via `--defer`.
- Trunk: verify SQL/YAML with
  `cd {wt} && /workspaces/teamster/.trunk/tools/trunk check --no-fix <files> </dev/null`
  before push (pre-commit hook only formats).

---

### Task 1: File follow-up issues for upstream duplicates

**Files:** none (GitHub only).

**Interfaces:**

- Produces: two issue numbers used in `TODO(#NNNN)` comments in Task 7.

- [ ] **Step 1: ASK THE USER for approval to open two issues** (repo rule: never
      open issues without asking). If declined, use `TODO:` without numbers in
      Task 7 and skip this task.

- [ ] **Step 2: Open the issues** via `mcp__github__issue_write` (owner
      `TEAMSchools`, repo `teamster`), labels `bug`, `dbt` plus source label:

  1. Title:
     `fix(iready): stg_iready__diagnostic_results lacks uniqueness test; duplicate and same-day retest rows`
     — body: at grain (project, student, year, round, subject, day) there are
     3,835 duplicate groups (max 16 rows); ~1,300 groups are byte-identical
     rows; staging yml has only a `not_null` on `student_id`. Downstream,
     `fct_assessment_scores_enrollment_scoped` dedupes defensively — remove that
     dedupe when fixed. Refs #3625.
  2. Title:
     `fix(renlearn): stg_renlearn__star fiscal-year partition overlap duplicates assessment_id rows`
     — body: ~2,296 `assessment_id`s appear in two
     `_dagster_partition_fiscal_year` partitions with identical data columns;
     plus no uniqueness test. Downstream fact dedupes defensively — remove when
     fixed. Refs #3625.

- [ ] **Step 3: Record the two issue numbers** for Task 7's TODO comments.

---

### Task 2: iReady intermediate — additive columns

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/iready/intermediate/int_iready__diagnostic_results.sql`
- Modify:
  `{wt}/src/dbt/kipptaf/models/iready/intermediate/properties/int_iready__diagnostic_results.yml`

**Interfaces:**

- Produces: columns `_dbt_source_project` (string; values `kippnewark`,
  `kippcamden`, `kippmiami`, ...) and `illuminate_subject` (string; `Text Study`
  | `Mathematics`) on `int_iready__diagnostic_results`. Consumed by Tasks 5–8.

- [ ] **Step 1: Add the two columns to the final SELECT.** In the final select
      (starts `select wc.*,`), after the line
      `right(rt.code, 1) as round_number,` insert:

```sql
    {{ extract_code_location("wc") }} as _dbt_source_project,
```

and immediately after the `end as iready_proficiency,` case block insert:

```sql
    case
        wc.subject when 'Reading' then 'Text Study' when 'Math' then 'Mathematics'
    end as illuminate_subject,
```

- [ ] **Step 2: Add both columns to the properties yml** `columns:` list (they
      are documentation entries; this model has no enforced contract):

```yaml
- name: _dbt_source_project
  data_type: string
  description: >-
    Dagster code location (kippnewark, kippcamden, kippmiami, ...) extracted
    from the crosswalk-rewritten _dbt_source_relation. Promoted here per the
    marts _dbt_source_project pattern so consumers join and hash a materialized
    column.
- name: illuminate_subject
  data_type: string
  description: >-
    Course-subject mapping used by the section-enrollment resolver — Reading
    maps to Text Study, Math to Mathematics. Matches the illuminate_subject
    convention in int_pearson__all_assessments and int_fldoe__all_assessments.
```

- [ ] **Step 3: Build and verify:**

```bash
uv run dbt build --select int_iready__diagnostic_results \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: model builds green. Then via BigQuery MCP:

```sql
select _dbt_source_project, illuminate_subject, count(*) as n_rows,
from `teamster-332318.zz_cbini_kipptaf_iready.int_iready__diagnostic_results`
group by 1, 2
```

Expected: only (`kipp*`, `Text Study`/`Mathematics`) combos, no NULL
`illuminate_subject`; NULL `_dbt_source_project` only where the crosswalk missed
(should be ~0).

- [ ] **Step 4: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/iready
git -C {wt} commit -m "feat(iready): add _dbt_source_project and illuminate_subject to diagnostic results

Refs #3625"
```

---

### Task 3: STAR rollup — additive columns

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/renlearn/intermediate/int_renlearn__star_rollup.sql`
- Modify:
  `{wt}/src/dbt/kipptaf/models/renlearn/intermediate/properties/int_renlearn__star_rollup.yml`

**Interfaces:**

- Produces: columns `completed_date` (DATE), `percentile_rank` (int64),
  `assessment_id` (string), `_dbt_source_project` (string), `illuminate_subject`
  (string) on `int_renlearn__star_rollup`. Existing columns and row set
  unchanged. Consumed by Tasks 5–8.

- [ ] **Step 1: Replace the model SQL** with (the crosswalk join requires
      aliasing every existing column with `s.`; window functions unchanged):

```sql
select
    s.student_display_id,
    s.state_benchmark_category_level,
    s.state_benchmark_category_name,
    s.state_benchmark_proficient,
    s.district_benchmark_category_level,
    s.district_benchmark_category_name,
    s.district_benchmark_proficient,
    s.unified_score,
    s.screening_period_window_name,
    s.percentile_rank,
    s.assessment_id,

    lc.location_dagster_code_location as _dbt_source_project,

    safe_cast(left(s.school_year, 4) as int) as academic_year,

    safe_cast(if(s.grade = 'K', '0', s.grade) as int) as grade_level,

    cast(left(s.completed_date_local, 10) as date) as completed_date,

    case
        when s.state_benchmark_proficient = 'Yes'
        then 1
        when s.state_benchmark_proficient = 'No'
        then 0
    end as is_state_benchmark_proficient_int,

    case
        when s.district_benchmark_proficient = 'Yes'
        then 1
        when s.district_benchmark_proficient = 'No'
        then 0
    end as is_district_benchmark_proficient_int,

    case
        when s._dagster_partition_subject = 'SM'
        then 'Math'
        when s._dagster_partition_subject = 'SR'
        then 'Reading'
        when s._dagster_partition_subject = 'SEL'
        then 'Early Literacy'
    end as star_subject,

    case
        when s._dagster_partition_subject = 'SM'
        then 'Math'
        when s.grade = 'K' and s._dagster_partition_subject = 'SEL'
        then 'ELA'
        when s._dagster_partition_subject = 'SR'
        then 'ELA'
    end as star_discipline,

    if(
        s._dagster_partition_subject = 'SM', 'Mathematics', 'Text Study'
    ) as illuminate_subject,

    row_number() over (
        partition by
            s.student_display_id,
            s._dagster_partition_subject,
            s.school_year,
            s.screening_period_window_name
        order by s.completed_date desc
    ) as rn_subj_round,

    row_number() over (
        partition by
            s.student_display_id,
            s._dagster_partition_subject,
            s.school_year,
            s.screening_period_window_name
        order by s.completed_date desc
    ) as rn_subj_year,
from {{ ref("stg_renlearn__star") }} as s
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on s.school_name = lc.location_name
where s.deactivation_reason is null
```

Notes: `illuminate_subject` maps Reading AND Early Literacy to `Text Study` (all
reading-family scores resolve to ELA sections — per spec). `completed_date`
casts the LOCAL datetime string's date part (`completed_date_local`, format
`YYYY-MM-DD HH:MM:SS.mmm`). Do NOT change the two `row_number()` definitions
(existing consumers filter on them; ordering by the raw string
`s.completed_date` is lexicographically correct for ISO datetimes).

- [ ] **Step 2: Add the five new columns to the properties yml** `columns:`
      list:

```yaml
- name: percentile_rank
  data_type: int64
  description: >-
    National percentile rank for the attempt, passed through from
    stg_renlearn__star.
- name: assessment_id
  data_type: string
  description: >-
    Renaissance per-attempt assessment identifier, passed through from
    stg_renlearn__star. Used downstream as a deterministic dedupe tiebreaker.
- name: _dbt_source_project
  data_type: string
  description: >-
    Dagster code location resolved via int_people__location_crosswalk on
    school_name. Required because NJ districts share one Renaissance instance
    (kippnj), so the source relation cannot identify the district. NULL when the
    school name has no crosswalk alias.
- name: completed_date
  data_type: date
  description: >-
    Local-time completion date of the attempt, cast from the
    completed_date_local datetime string.
- name: illuminate_subject
  data_type: string
  description: >-
    Course-subject mapping used by the section-enrollment resolver — Math
    partitions map to Mathematics; Reading and Early Literacy map to Text Study.
```

Check `assessment_id`'s actual staging type first
(`grep -A1 'name: assessment_id' {wt}/src/dbt/kipptaf/models/renlearn/staging/properties/stg_renlearn__star.yml`)
and mirror it.

- [ ] **Step 3: Build and verify:**

```bash
uv run dbt build --select int_renlearn__star_rollup \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Then via BigQuery MCP:

```sql
select
    _dbt_source_project,
    illuminate_subject,

    count(*) as n_rows,
    countif(completed_date is null) as n_null_date,
    countif(percentile_rank is null) as n_null_pr,
from `teamster-332318.zz_cbini_kipptaf_renlearn.int_renlearn__star_rollup`
group by 1, 2
```

Expected: rows land under a `kipp*` project (currently Miami-only, one school);
`n_null_date` ~8 (rows with null `completed_date_local`); row count unchanged
from before the edit (~9,843 active rows).

- [ ] **Step 4: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/renlearn
git -C {wt} commit -m "feat(renlearn): add project, subject mapping, date, percentile to star rollup

Refs #3625"
```

---

### Task 4: Amplify intermediate — additive columns

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/amplify/intermediate/int_amplify__all_assessments.sql`
- Modify:
  `{wt}/src/dbt/kipptaf/models/amplify/intermediate/properties/int_amplify__all_assessments.yml`

**Interfaces:**

- Produces: columns `_dbt_source_project` (string,
  `concat('kipp', lower(region))`) and `illuminate_subject` (string, constant
  `Text Study`) on `int_amplify__all_assessments`. Consumed by Tasks 5–8.

- [ ] **Step 1: Add two columns to BOTH final union branches** (the model ends
      in two `select ... from max_score as s left join probe_eligible_tag as p`
      branches — Benchmark and PM). In EACH branch, immediately after the line
      `p.eoy as eoy_composite,` insert (identical position in both branches —
      UNION ALL aligns positionally):

```sql
    'Text Study' as illuminate_subject,

    concat('kipp', lower(s.region)) as _dbt_source_project,
```

- [ ] **Step 2: Add both columns to the properties yml** `columns:` list:

```yaml
- name: illuminate_subject
  data_type: string
  description: >-
    Course-subject mapping used by the section-enrollment resolver. All DIBELS
    measures are reading-family, so this is constant Text Study.
- name: _dbt_source_project
  data_type: string
  description: >-
    Dagster code location derived from the region name (kipp + lowercased
    region). Promoted here per the marts _dbt_source_project pattern so
    consumers join and hash a materialized column.
```

- [ ] **Step 3: Build and verify:**

```bash
uv run dbt build --select int_amplify__all_assessments \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Then via BigQuery MCP:

```sql
select _dbt_source_project, count(*) as n_rows,
from `teamster-332318.zz_cbini_kipptaf_amplify.int_amplify__all_assessments`
group by 1
```

Expected: exactly `kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`.

- [ ] **Step 4: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/amplify
git -C {wt} commit -m "feat(amplify): add _dbt_source_project and illuminate_subject to all_assessments

Refs #3625"
```

---

### Task 5: Resolver — vendor score branches

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`
- Modify:
  `{wt}/src/dbt/kipptaf/models/assessments/intermediate/properties/int_assessments__resolved_section_enrollments.yml`

**Interfaces:**

- Consumes: Task 2–4 columns (`_dbt_source_project`, `illuminate_subject`).
- Produces: resolver rows with `source_type` in (`iready`, `star`, `dibels`),
  resolving on `subject_area` = the vendor `illuminate_subject`,
  `administration_period` = vendor window, `academic_year` = vendor year. Task
  8's fact joins these on
  `(powerschool_student_number, academic_year, administration_period, subject_area, _dbt_source_project, source_type)`.

- [ ] **Step 1: Add three score CTEs** after the `state_fl_scores` CTE (before
      the `scores` CTE):

```sql
    -- iReady diagnostics. test_round is the reporting-terms IR window (BOY /
    -- MOY / EOY / Outside Round); illuminate_subject maps Reading -> Text
    -- Study, Math -> Mathematics upstream.
    iready_scores as (
        select
            student_id as powerschool_student_number,
            academic_year_int as academic_year,
            test_round as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completion_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'iready' as source_type,
        from {{ ref("int_iready__diagnostic_results") }}
        where completion_date is not null and overall_scale_score is not null
    ),

    -- STAR attempts. screening_period_window_name is the vendor window (Fall /
    -- Winter / Spring); rows without a crosswalk-resolved project cannot join
    -- course enrollments and are dropped (out of scope).
    star_scores as (
        select
            student_display_id as powerschool_student_number,
            academic_year,
            screening_period_window_name as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            completed_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'star' as source_type,
        from {{ ref("int_renlearn__star_rollup") }}
        where
            completed_date is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- DIBELS benchmark composites. One row per student x benchmark window
    -- (BOY / MOY / EOY); PM probes and subskill measures are out of scope.
    dibels_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            `period` as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            client_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'dibels' as source_type,
        from {{ ref("int_amplify__all_assessments") }}
        where
            assessment_type = 'Benchmark'
            and measure_standard = 'Composite'
            and client_date is not null
    ),
```

- [ ] **Step 2: Union them into the `scores` CTE** — append three
      `union all select <same 8 columns> from <cte>` blocks matching the
      existing three, e.g.:

```sql
        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from iready_scores
```

(repeat for `star_scores` and `dibels_scores`).

- [ ] **Step 3: Update the properties yml**: extend the `source_type`
      `accepted_values` to
      `values: [internal, state_nj, state_fl, iready, star, dibels]`, extend the
      `source_type` column description with the three new values, and extend the
      model `description` to mention the vendor sources.

- [ ] **Step 4: Build and verify:**

```bash
uv run dbt build --select int_assessments__resolved_section_enrollments \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Then via BigQuery MCP — resolver hit-rate per new source:

```sql
select source_type, resolution_type, count(*) as n_rows,
from `teamster-332318.zz_cbini_kipptaf_assessments.int_assessments__resolved_section_enrollments`
where source_type in ('iready', 'star', 'dibels')
group by 1, 2
```

Expected: non-zero rows for all three source types; DIBELS mostly
`homeroom`-resolved (K–2). If a source returns 0 rows, STOP — the subject
mapping or join keys are wrong; do not proceed to Task 8.

- [ ] **Step 5: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/assessments
git -C {wt} commit -m "feat(dbt): resolve section enrollments for iready, star, dibels scores

Refs #3625"
```

---

### Task 6: `dim_assessments` — vendor branches

**Files:**

- Modify: `{wt}/src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql`

**Interfaces:**

- Produces: dim rows with `assessment_key` =
  `generate_surrogate_key([assessment_type, module_code, source_assessment_id, test_type])`
  for the vendor values below. Task 7/8 hash the same inputs. Vendor values:
  (`iready`, module `subject`), (`star`, module `star_subject`), (`dibels`,
  module `measure_standard` = `Composite`);
  `source_assessment_id`/`test_type`/`module_type`/`grade_level` NULL,
  `is_internal_assessment` false, `assessment_scope` `'enrollment'`.

- [ ] **Step 1: Add three CTEs** after `state_fl_science` (before
      `college_assessments`):

```sql
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    iready_assessments as (
        select distinct
            subject as subject_area,
            subject as module_code,

            'iready' as assessment_type,
            'i-Ready Diagnostic' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            if(subject = 'Math', 'Math', 'ELA') as scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    star_assessments as (
        select distinct
            star_subject as subject_area,
            star_subject as module_code,

            'star' as assessment_type,
            'STAR' as title,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            if(star_subject = 'Math', 'Math', 'ELA') as scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_renlearn__star_rollup") }}
        where completed_date is not null and unified_score is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    dibels_assessments as (
        select distinct
            measure_standard as module_code,

            'Reading' as subject_area,
            'dibels' as assessment_type,
            'DIBELS' as title,
            'ELA' as scope,
            false as is_internal_assessment,
            'enrollment' as assessment_scope,

            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as module_type,
            cast(null as string) as combined_academic_subject,
            cast(null as string) as aligned_academic_subject,
            cast(null as string) as credit_category,
            cast(null as string) as test_type,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),
```

- [ ] **Step 2: Add three union entries** in `all_assessments_unioned` (after
      the `state_fl_science` entry):

```sql
        union all
        select {{ union_cols }},
        from iready_assessments
        union all
        select {{ union_cols }},
        from star_assessments
        union all
        select {{ union_cols }},
        from dibels_assessments
```

- [ ] **Step 3: Build and verify:**

```bash
uv run dbt build --select dim_assessments \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build + `unique` test on `assessment_key` green. Then:

```sql
select `type`, module_code, title, academic_subject,
from `teamster-332318.zz_cbini_kipptaf_marts.dim_assessments`
where `type` in ('iready', 'star', 'dibels')
```

Expected: 2 iready rows (Reading, Math), 3 star rows (Reading, Math, Early
Literacy), 1 dibels row (Composite).

- [ ] **Step 4: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql
git -C {wt} commit -m "feat(dbt): add iready, star, dibels to dim_assessments

Refs #3625"
```

---

### Task 7: `dim_assessment_administrations` — vendor branches

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql`

**Interfaces:**

- Produces: dim rows with `assessment_administration_key` =
  `generate_surrogate_key([assessment_type, module_code, administered_date, academic_year, _dbt_source_project, administration_period, source_assessment_id, test_type])`
  where `administered_date` / `source_assessment_id` / `test_type` are NULL for
  vendor rows. Task 8 hashes the same inputs (`null` literals for the NULL
  slots).

- [ ] **Step 1: Add three CTEs** after `state_fl_science_administrations`
      (before `college_administrations`):

```sql
    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- iReady: one administration per (subject, test_round, academic_year,
    -- _dbt_source_project).
    iready_administrations as (
        select distinct
            subject as subject_area,
            subject as module_code,
            academic_year_int as academic_year,
            test_round as administration_period,
            _dbt_source_project,

            'iready' as assessment_type,
            'i-Ready Diagnostic' as title,

            if(subject = 'Math', 'Math', 'ELA') as scope,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null and _dbt_source_project is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- STAR: one administration per (star_subject, screening window,
    -- academic_year, _dbt_source_project).
    star_administrations as (
        select distinct
            star_subject as subject_area,
            star_subject as module_code,
            academic_year,
            screening_period_window_name as administration_period,
            _dbt_source_project,

            'star' as assessment_type,
            'STAR' as title,

            if(star_subject = 'Math', 'Math', 'ELA') as scope,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("int_renlearn__star_rollup") }}
        where
            completed_date is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    -- DIBELS: one administration per (benchmark window, academic_year,
    -- _dbt_source_project); module_code is the Composite measure.
    dibels_administrations as (
        select distinct
            measure_standard as module_code,
            academic_year,
            `period` as administration_period,
            _dbt_source_project,

            'Reading' as subject_area,
            'dibels' as assessment_type,
            'DIBELS' as title,
            'ELA' as scope,

            cast(null as date) as administered_date,
            cast(null as int64) as grade_level,
            cast(null as int64) as source_assessment_id,
            cast(null as string) as test_type,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),
```

Note the inner `where assessment_type = 'Benchmark'` filters the SOURCE column
`int_amplify__all_assessments.assessment_type` (Benchmark vs PM) — a different
thing from the `'dibels' as assessment_type` output constant.

- [ ] **Step 2: Add three union entries** in `all_administrations` (after the
      `state_fl_science_administrations` entry), matching the existing pattern:

```sql
        union all
        select {{ union_cols }},
        from iready_administrations
        union all
        select {{ union_cols }},
        from star_administrations
        union all
        select {{ union_cols }},
        from dibels_administrations
```

- [ ] **Step 3: Build and verify:**

```bash
uv run dbt build --select dim_assessment_administrations \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: build + PK `unique` test green (vendor rows cannot collide with
existing rows — `assessment_type` is in the hash). Then sanity — the dim doesn't
expose `assessment_type`, so count new rows as the delta vs prod:

```sql
select administration_period, count(*) as n_rows,
from `teamster-332318.zz_cbini_kipptaf_marts.dim_assessment_administrations`
where
    administration_period
    in ('BOY', 'MOY', 'EOY', 'Fall', 'Winter', 'Spring', 'Outside Round')
group by 1
```

Expected: non-zero counts for the vendor windows (BOY/MOY/EOY also appear for
existing sources — compare against the same query on
`kipptaf_marts.dim_assessment_administrations` to confirm growth).

- [ ] **Step 4: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql
git -C {wt} commit -m "feat(dbt): add iready, star, dibels to dim_assessment_administrations

Refs #3625"
```

---

### Task 8: Fact — vendor branches + `growth_percentile`

**Files:**

- Modify:
  `{wt}/src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`
- Modify:
  `{wt}/src/dbt/kipptaf/models/marts/facts/properties/fct_assessment_scores_enrollment_scoped.yml`

**Interfaces:**

- Consumes: resolver `source_type` values and join keys (Task 5); dim hash
  compositions (Tasks 6–7); issue numbers from Task 1 for TODOs.
- Produces: fact rows with `score_source` values hashed into
  `assessment_score_key`; new contract column `growth_percentile` (numeric).

- [ ] **Step 1: Add vendor CTEs** after the `state_union` CTE (inside the `with`
      block; remember to add a comma after the `state_union` closing paren).
      Replace `#NNNN1` / `#NNNN2` with Task 1's issue numbers:

```sql
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    iready_scores_raw as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            subject as module_code,
            illuminate_subject,
            test_round as administration_period,
            completion_date as test_date,
            `start_date`,
            _dbt_source_project,

            overall_relative_placement as proficiency_level,

            'iready' as score_source,

            cast(overall_scale_score as numeric) as scale_score,
            cast(percentile as numeric) as growth_percentile,

            overall_relative_placement_int >= 4 as is_mastery,
        from {{ ref("int_iready__diagnostic_results") }}
        where overall_scale_score is not null
    ),

    -- TODO(#NNNN1): stg_iready__diagnostic_results has no uniqueness test;
    -- same-day retests and duplicate rows exist upstream. Remove this dedupe
    -- when staging is fixed.
    iready_scores as (
        {{
            dbt_utils.deduplicate(
                relation="iready_scores_raw",
                partition_by="""
                    _dbt_source_project,
                    student_number,
                    academic_year,
                    administration_period,
                    module_code,
                    test_date
                """,
                order_by="start_date desc, scale_score desc",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    star_scores_raw as (
        select
            student_display_id as student_number,
            academic_year,
            star_subject as module_code,
            illuminate_subject,
            screening_period_window_name as administration_period,
            completed_date as test_date,
            assessment_id,
            _dbt_source_project,

            state_benchmark_category_name as proficiency_level,

            'star' as score_source,

            cast(unified_score as numeric) as scale_score,
            cast(percentile_rank as numeric) as growth_percentile,

            state_benchmark_proficient = 'Yes' as is_mastery,
        from {{ ref("int_renlearn__star_rollup") }}
        where
            completed_date is not null
            and unified_score is not null
            and _dbt_source_project is not null
    ),

    -- TODO(#NNNN2): stg_renlearn__star holds fiscal-year re-pull duplicates
    -- (same assessment_id in two partitions) and same-day retests. Remove
    -- this dedupe when staging is fixed.
    star_scores as (
        {{
            dbt_utils.deduplicate(
                relation="star_scores_raw",
                partition_by="""
                    _dbt_source_project,
                    student_number,
                    academic_year,
                    administration_period,
                    module_code,
                    test_date
                """,
                order_by="scale_score desc, assessment_id desc",
            )
        }}
    ),

    -- DIBELS benchmark composites are unique at this grain upstream
    -- (verified); no dedupe needed.
    dibels_scores as (
        select
            student_number,
            academic_year,
            measure_standard as module_code,
            illuminate_subject,
            `period` as administration_period,
            client_date as test_date,
            _dbt_source_project,

            measure_standard_level as proficiency_level,

            'dibels' as score_source,

            cast(measure_standard_score as numeric) as scale_score,
            cast(measure_percentile as numeric) as growth_percentile,

            measure_standard_level_int >= 3 as is_mastery,
        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark' and measure_standard = 'Composite'
    ),

    vendor_all as (
        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from iready_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from star_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            illuminate_subject,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            growth_percentile,
            is_mastery,
        from dibels_scores
    )
```

(The `deduplicate` output CTEs carry the raw CTEs' full column list, so the
`vendor_all` enumerations resolve. `iready_scores` retains `start_date` and
`star_scores` retains `assessment_id` — they are dropped by `vendor_all`'s
explicit column list.)

- [ ] **Step 2: Add `growth_percentile` to both existing final branches.** In
      the internal branch, after `ia.percent_correct,` insert:

```sql
    cast(null as numeric) as growth_percentile,
```

In the state branch, after `su.percent_correct,` insert the same line. (Position
matters — UNION ALL aligns by position; it must sit between `percent_correct`
and `proficiency_level` in every branch.)

- [ ] **Step 3: Append the vendor final branch** at the end of the model:

```sql
union all

/* vendor assessments (iReady, STAR, DIBELS) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va._dbt_source_project",
                "va.student_number",
                "va.academic_year",
                "va.administration_period",
                "va.module_code",
                "va.test_date",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va.module_code",
                "null",
                "va.academic_year",
                "va._dbt_source_project",
                "va.administration_period",
                "null",
                "null",
            ]
        )
    }} as assessment_administration_key,

    sr.student_section_enrollment_key,

    va.test_date as test_date_key,

    va.scale_score,

    cast(null as numeric) as percent_correct,

    va.growth_percentile,
    va.proficiency_level,
    va.is_mastery,

    cast(null as string) as response_type,
    cast(null as string) as response_type_code,
    cast(null as string) as response_type_description,
    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as numeric) as performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from vendor_all as va
-- the resolver keys vendor scores on illuminate_subject (the vendor->course
-- subject mapping), not the raw vendor subject the assessment_score_key
-- hashes. INNER scopes the fact to vendor scores with a resolved section.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on va.student_number = sr.powerschool_student_number
    and va.academic_year = sr.academic_year
    and va.administration_period = sr.administration_period
    and va.illuminate_subject = sr.subject_area
    and va._dbt_source_project = sr._dbt_source_project
    and va.score_source = sr.source_type
```

Positional check against the other branches' SELECT lists: keys, enrollment key,
`test_date_key`, `scale_score`, `percent_correct`, `growth_percentile`,
`proficiency_level`, `is_mastery`, five response NULLs +
`performance_band_label_number`, `enrollment_resolution` — must match the column
ORDER of the internal branch after Step 2.

- [ ] **Step 4: Update the properties yml:**
  - Model `description`: replace "Covers internal Illuminate assessments and
    state assessments (NJSLA, NJGPA, FAST)." with "Covers internal Illuminate
    assessments, state assessments (NJSLA, NJGPA, FAST), and vendor benchmark
    assessments (i-Ready Diagnostic, STAR, DIBELS Composite)."
  - Add after the `percent_correct` column entry:

```yaml
- name: growth_percentile
  data_type: numeric
  description: >-
    National percentile for the attempt where the vendor provides one (i-Ready
    percentile, STAR percentile rank, DIBELS measure percentile). Null for
    internal and state assessments.
```

- [ ] **Step 5: Build and verify:**

```bash
uv run dbt build --select fct_assessment_scores_enrollment_scoped \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: contract passes; PK `unique` + `not_null` tests green.
Relationship-test caveat: warnings against `dim_student_section_enrollments` or
the dims may be stale-dev-defer false positives (see `src/dbt/CLAUDE.md` "Stale
dev tables shadow --defer") — if any fire, rebuild the parent dims into dev
(`--select dim_assessments dim_assessment_administrations`) or verify orphans
against prod before treating as real.

- [ ] **Step 6: Validate FK population and per-source counts** via BigQuery MCP
      (reproducing the score_source from the hash is unnecessary — recompute
      per-source expected counts from the resolver side):

```sql
select
    countif(assessment_administration_key is null) as n_null_admin_fk,
    countif(student_section_enrollment_key is null) as n_null_enroll_fk,
    countif(growth_percentile is not null) as n_growth_pop,

    count(*) as n_rows,
from `teamster-332318.zz_cbini_kipptaf_marts.fct_assessment_scores_enrollment_scoped`
```

Expected: 0 null FKs; `n_growth_pop` > 0; `n_rows` grew vs prod
(`select count(*) from kipptaf_marts.fct_assessment_scores_enrollment_scoped`)
by roughly the resolver-matched vendor volume (order of magnitude: iReady 100k+,
DIBELS tens of thousands, STAR thousands).

- [ ] **Step 7: Commit:**

```bash
git -C {wt} add src/dbt/kipptaf/models/marts/facts
git -C {wt} commit -m "feat(dbt): add iready, star, dibels to fct_assessment_scores_enrollment_scoped

Closes #3625"
```

---

### Task 9: Full-graph validation, trunk, push, PR

**Files:** none new.

- [ ] **Step 1: Merge main and full build** of all touched models plus immediate
      children:

```bash
git -C {wt} fetch origin main && git -C {wt} merge origin/main
uv run dbt build \
  --select int_iready__diagnostic_results int_renlearn__star_rollup \
    int_amplify__all_assessments int_assessments__resolved_section_enrollments \
    dim_assessments dim_assessment_administrations \
    fct_assessment_scores_enrollment_scoped \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all green (warn-severity orphan warnings evaluated per Task 8 Step 5
caveat).

- [ ] **Step 2: Verify existing downstream consumers of the edited intermediates
      still compile** (additive columns can't break enumerating consumers; this
      guards against an accidental non-additive edit):

```bash
uv run dbt ls --select int_renlearn__star_rollup+1 int_iready__diagnostic_results+1 \
    int_amplify__all_assessments+1 --project-dir {wt}/src/dbt/kipptaf --target dev
uv run dbt compile --select int_renlearn__star_rollup+1 int_iready__diagnostic_results+1 \
    int_amplify__all_assessments+1 \
  --project-dir {wt}/src/dbt/kipptaf --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: compile green (additive columns cannot break enumerating consumers;
this guards against accidental non-additive edits).

- [ ] **Step 3: Trunk check all touched files:**

```bash
cd {wt} && /workspaces/teamster/.trunk/tools/trunk check --no-fix \
  src/dbt/kipptaf/models/iready/intermediate/int_iready__diagnostic_results.sql \
  src/dbt/kipptaf/models/renlearn/intermediate/int_renlearn__star_rollup.sql \
  src/dbt/kipptaf/models/amplify/intermediate/int_amplify__all_assessments.sql \
  src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessments.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_assessment_administrations.sql \
  src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql \
  docs/superpowers/specs/2026-07-13-vendor-assessments-enrollment-scoped-fact-design.md \
  docs/superpowers/plans/2026-07-13-vendor-assessments-enrollment-scoped-fact.md \
  </dev/null
```

Also check the edited `.yml` properties files. Expected: no issues (fix any
sqlfluff findings before push).

- [ ] **Step 4: Push and open the PR** (confirm with the user before pushing if
      anything looks off):

```bash
git -C {wt} push -u origin cbini/feat/claude-fct-assessment-scores-vendor-sources
```

Create the PR with `mcp__github__create_pull_request` using
`.github/pull_request_template.md` as the body skeleton; body must include
`Closes #3625`. Title:
`feat(dbt): add iReady, STAR, DIBELS to fct_assessment_scores_enrollment_scoped`.

- [ ] **Step 5: Monitor dbt Cloud CI** (commit STATUS, not check runs) plus
      Trunk/CodeQL check runs. After CI passes, fetch warnings with
      `mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` and run
      the marts pre-merge checklist (`src/dbt/kipptaf/models/marts/CLAUDE.md`):
      diamond-path scan, rubric scan, CI-warning triage, project-board bonus
      scan.

- [ ] **Step 6: Post-CI validation on the PR-branch schema** (dataset
      `dbt_cloud_pr_<job_definition_id>_<pr>_<schema>`): re-run the Task 8 Step
      6 query against the PR-branch fact; compare per-window vendor counts to
      the dev-schema numbers.
