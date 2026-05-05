# Batch M Grades Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve five batch-M issues atomically: source-data Paterson fix,
internal-consistency fix in `dim_terms`, defensive uniqueness test on RT terms,
regex region-extraction replacement in three mart files, and split of
polymorphic `score` into Ed-Fi-aligned typed columns.

**Architecture:** All changes outside `marts/` are strictly additive. The
grades-mart join chain reads region from `stg_google_sheets__people__locations`
via a new materialized `_dbt_source_project` column on three upstream union
models (targeted subset of #3142). The intermediate
`int_powerschool__gradebook_assignments_scores` gains `points_earned` /
`numeric_grade_earned` alongside the legacy `score_entered` / `scoretype`; the
mart `fct_grades_assignments` exposes the typed columns and drops the
polymorphic ones.

**Tech Stack:** dbt 1.11 on BigQuery; Python ≥3.13 via `uv run`. Worktree at
`.worktrees/cbini-refactor-claude-batch-m-grades-hardening/`. dbt project:
`src/dbt/kipptaf/`.

**Spec:**
[`docs/superpowers/specs/2026-05-05-batch-m-grades-hardening-design.md`](../specs/2026-05-05-batch-m-grades-hardening-design.md)

---

## Working environment

All commands run from the worktree:

```bash
WT=/workspaces/teamster/.worktrees/cbini-refactor-claude-batch-m-grades-hardening
DBT="uv run dbt"
DBT_DIR=$WT/src/dbt/kipptaf
```

For `git`, prefix every call with `git -C $WT`. For dbt, append
`--project-dir $DBT_DIR`. Trunk pre-commit/pre-push hooks fire automatically;
never run `trunk fmt` or `trunk check` manually.

---

### Task 1: Add `_dbt_source_project` to `base_powerschool__final_grades`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__final_grades.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__final_grades.yml`

- [ ] **Step 1: Wrap the bare `union_relations` in a CTE and append
      `_dbt_source_project`**

Replace the entire contents of `base_powerschool__final_grades.sql` with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
from union_relations as ur
```

- [ ] **Step 2: Add the new column to the properties YAML**

In `base_powerschool__final_grades.yml`, add immediately after the
`_dbt_source_relation` entry (line 6-7):

```yaml
- name: _dbt_source_project
  data_type: string
  description: >-
    District code-location extracted once from `_dbt_source_relation` (e.g.,
    `kippnewark`, `kippcamden`). Materialized join key for cross-region region
    lookups against
    `stg_google_sheets__people__locations.dagster_code_location`.
```

- [ ] **Step 3: Build the model**

```bash
$DBT build --select base_powerschool__final_grades --project-dir $DBT_DIR --exclude resource_type:test
```

Expected: model rebuilds, no errors.

- [ ] **Step 4: Verify column populated**

Via BigQuery MCP:

```sql
select _dbt_source_project, count(*) as n
from `teamster-332318.kipptaf_powerschool.base_powerschool__final_grades`
group by 1
order by 1
```

Expected: 3 rows for `kippnewark`, `kippcamden`, `kippmiami` with non-zero
counts.

- [ ] **Step 5: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/powerschool/base/base_powerschool__final_grades.sql src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__final_grades.yml
git -C $WT commit -m "refactor(dbt): add _dbt_source_project to base_powerschool__final_grades

Targeted #3142 subset for batch M. Materializes
extract_code_location() once per row so downstream mart joins read
the column directly instead of recomputing the regex per query."
```

---

### Task 2: Add `_dbt_source_project` to `base_powerschool__sections`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/base/base_powerschool__sections.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__sections.yml`

- [ ] **Step 1: Add `_dbt_source_project` to the final SELECT**

In `base_powerschool__sections.sql`, replace the final select (lines 15-20)
with:

```sql
select
    ur.*,
    {{ extract_code_location("ur") }} as _dbt_source_project,
    if(cx.ap_course_subject is not null, true, false) as is_ap_course,
from union_relations as ur
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
    on ur.courses_dcid = cx.coursesdcid
    and {{ union_dataset_join_clause(left_alias="ur", right_alias="cx") }}
```

- [ ] **Step 2: Add the new column to the properties YAML**

In `base_powerschool__sections.yml`, add immediately after
`_dbt_source_relation` (line 6-7):

```yaml
- name: _dbt_source_project
  data_type: string
  description: >-
    District code-location extracted once from `_dbt_source_relation` (e.g.,
    `kippnewark`, `kippcamden`). Materialized join key for cross-region region
    lookups against
    `stg_google_sheets__people__locations.dagster_code_location`.
```

- [ ] **Step 3: Build the model**

```bash
$DBT build --select base_powerschool__sections --project-dir $DBT_DIR --exclude resource_type:test
```

Expected: rebuilds without error.

- [ ] **Step 4: Verify column populated**

```sql
select _dbt_source_project, count(*) as n
from `teamster-332318.kipptaf_powerschool.base_powerschool__sections`
group by 1
order by 1
```

Expected: 4 rows (`kippnewark`, `kippcamden`, `kippmiami`, `kipppaterson`) with
non-zero counts.

- [ ] **Step 5: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/powerschool/base/base_powerschool__sections.sql src/dbt/kipptaf/models/powerschool/base/properties/base_powerschool__sections.yml
git -C $WT commit -m "refactor(dbt): add _dbt_source_project to base_powerschool__sections

Targeted #3142 subset for batch M."
```

---

### Task 3: Add `_dbt_source_project` to `stg_powerschool__schools`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__schools.yml`

- [ ] **Step 1: Add `_dbt_source_project` to the final SELECT**

In `stg_powerschool__schools.sql`, replace the final select (lines 15-21) with:

```sql
select
    u.*,
    {{ extract_code_location("u") }} as _dbt_source_project,
    loc.location_key,
from unioned as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_number = loc.powerschool_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
```

- [ ] **Step 2: Add the new column to the properties YAML**

In `stg_powerschool__schools.yml`, add immediately before the `location_key`
entry (line 6-7):

```yaml
- name: _dbt_source_project
  data_type: string
  description: >-
    District code-location extracted once from `_dbt_source_relation` (e.g.,
    `kippnewark`, `kippcamden`). Materialized join key for cross-region region
    lookups against
    `stg_google_sheets__people__locations.dagster_code_location`.
```

- [ ] **Step 3: Build the model**

```bash
$DBT build --select stg_powerschool__schools --project-dir $DBT_DIR --exclude resource_type:test
```

Expected: rebuilds without error.

- [ ] **Step 4: Verify column populated**

```sql
select _dbt_source_project, count(*) as n
from `teamster-332318.kipptaf_powerschool.stg_powerschool__schools`
group by 1
order by 1
```

Expected: 4 rows for the four district code-locations.

- [ ] **Step 5: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__schools.sql src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__schools.yml
git -C $WT commit -m "refactor(dbt): add _dbt_source_project to stg_powerschool__schools

Targeted #3142 subset for batch M."
```

---

### Task 4: Fix Paterson CASE bug in `stg_google_sheets__reporting__terms`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__reporting__terms.sql`

- [ ] **Step 1: Add `'Paterson'` to the Paterson WHEN clause**

In `stg_google_sheets__reporting__terms.sql`, replace lines 11-12:

```sql
        when region in ('KIPP Paterson', 'Paterson')
        then 'Paterson'
```

(Was: `when region in ('KIPP Paterson')`)

- [ ] **Step 2: Build the model**

```bash
$DBT build --select stg_google_sheets__reporting__terms --project-dir $DBT_DIR --exclude resource_type:test
```

Expected: rebuilds without error.

- [ ] **Step 3: Verify Paterson rows now canonicalized**

```sql
select region as raw_region, city as canonical, count(*) as n
from `teamster-332318.kipptaf_google_sheets.stg_google_sheets__reporting__terms`
where region = 'Paterson' or city = 'Paterson'
group by 1, 2
order by 1, 2
```

Expected: row `(raw_region='Paterson', canonical='Paterson', n=30)` is now
present (previously `canonical=NULL`). Other Paterson row
`(raw_region='KIPP Paterson', canonical='Paterson', n=9)` unchanged.

- [ ] **Step 4: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/google/sheets/staging/stg_google_sheets__reporting__terms.sql
git -C $WT commit -m "fix(dbt): canonicalize bare 'Paterson' region in reporting terms

Closes #3691 (CASE-bug portion). Previously the WHEN clause matched
only 'KIPP Paterson'; 30 rows with raw region 'Paterson' had NULL city."
```

---

### Task 5: Add RT-grain uniqueness test to `stg_google_sheets__reporting__terms`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml`

- [ ] **Step 1: Add a model-level `data_tests` block**

In the YAML, insert immediately after the `description:` block (after line 8)
and before `columns:`:

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns:
          - name
          - school_id
          - region
          - powerschool_year_id
      config:
        severity: error
        where: "type = 'RT'"
```

- [ ] **Step 2: Run the new test**

```bash
$DBT test --select stg_google_sheets__reporting__terms --project-dir $DBT_DIR
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml
git -C $WT commit -m "test(dbt): add RT-grain uniqueness test to reporting terms

Closes #3738. Catches future drift in the RT term staging contract
at build time before any mart fan-out, replacing the originally
proposed mart-level qualify (which the project's no-manual-dedup
convention prohibits)."
```

---

### Task 6: Update `dim_terms` — replace regex region join (hash unchanged)

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml`

- [ ] **Step 1: Rewrite `dim_terms.sql`**

Replace the entire file contents with:

```sql
with
    terms as (select * from {{ ref("stg_google_sheets__reporting__terms") }}),

    location_regions as (
        select dagster_code_location, location_region,
        from {{ ref("stg_google_sheets__people__locations") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "t.`type`",
                "t.code",
                "t.`name`",
                "t.`start_date`",
                "t.region",
                "t.school_id",
            ]
        )
    }} as term_key,

    sch.location_key,

    t.`type`,
    t.code as term_code,
    t.`name` as term_name,
    t.`start_date`,
    t.end_date,
    t.academic_year,
    t.fiscal_year,
    t.grade_band,
    t.lockbox_date as data_freeze_date,
    t.is_current,
from terms as t
left join
    location_regions as lr
    on lr.location_region = t.city
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on t.school_id = sch.school_number
    and t.school_id <> 0
    and sch._dbt_source_project = lr.dagster_code_location
```

This change does two things in one model:

- Adds a `location_regions` CTE pulling
  `(dagster_code_location, location_region)` from canonical staging.
- Replaces the regex+initcap join on
  `regexp_extract(sch._dbt_source_relation, r'(kipp\w+)_')` with a direct read
  of `sch._dbt_source_project` (added in Task 3) joined transitively through
  `location_regions`.

The `term_key` hash inputs stay on `t.region` (raw) — region is load-bearing for
term-row uniqueness across nine consumer marts that hash from `rt.region`;
switching the hash on `dim_terms` alone would orphan their FKs.

- [ ] **Step 2: Promote `unique_dim_terms_term_key` severity**

In `dim_terms.yml`, the `term_key` `data_tests` block currently has:

```yaml
data_tests:
  - unique
  - not_null
```

Replace with:

```yaml
data_tests:
  - unique:
      config:
        severity: error
  - not_null:
      config:
        severity: error
```

- [ ] **Step 3: Build dim_terms and run its tests**

```bash
$DBT build --select dim_terms+1 --project-dir $DBT_DIR
```

Expected: model rebuilds; `unique_dim_terms_term_key` and the `relationships`
test on `location_key` both pass at error severity.

- [ ] **Step 4: Spot-check join coverage**

```sql
select
  countif(location_key is null) as null_loc,
  countif(location_key is not null) as has_loc,
  count(*) as total
from `teamster-332318.kipptaf.dim_terms`
```

Expected: roughly 2,500 has_loc, ~1,200 null_loc, ~3,750 total — close to
current production numbers, with ~30 additional has_loc rows from the Paterson
fix.

- [ ] **Step 5: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/dimensions/dim_terms.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml
git -C $WT commit -m "refactor(dbt): replace regex region join in dim_terms; promote unique test

Closes #3691 (dim_terms portion) and #3677 (test severity).
- Replaces brittle regexp_extract on _dbt_source_relation with a join
  on stg_google_sheets__people__locations via the new
  _dbt_source_project column (#3739).
- Promotes unique_dim_terms_term_key severity warn→error."
```

---

### Task 7: Replace regex region join in `fct_grades_term`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql`

- [ ] **Step 1: Add `location_regions` CTE and rewrite the join**

In `fct_grades_term.sql`, add a new CTE after the existing `reporting_terms` CTE
(insert after line 25, before `select`):

```sql
    location_regions as (
        select dagster_code_location, location_region,
        from {{ ref("stg_google_sheets__people__locations") }}
    )
```

Replace the join clause at line 117 from:

```sql
    and initcap(regexp_extract(fg._dbt_source_relation, r'kipp(\w+)_')) = rt.region
```

To:

```sql
    and rt.region = lr.location_region
```

And add a join to `location_regions` using `fg._dbt_source_project` (which Task
1 added). Insert immediately before the `left join reporting_terms` block
(around line 113):

```sql
inner join
    location_regions as lr
    on lr.dagster_code_location = fg._dbt_source_project
```

The fact join sequence becomes:
`base_powerschool__final_grades fg → student_enrollments → location_regions lr → reporting_terms rt`.

- [ ] **Step 2: Build the model and run tests**

```bash
$DBT build --select fct_grades_term --project-dir $DBT_DIR
```

Expected: rebuilds without error; `relationships` tests on `term_key` pass.

- [ ] **Step 3: Verify row count parity vs main**

```sql
select count(*) from `teamster-332318.kipptaf.fct_grades_term`
```

Expected: row count matches production — the join swap is value-equivalent.

- [ ] **Step 4: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql
git -C $WT commit -m "refactor(dbt): replace regex region join in fct_grades_term

Closes #3739 (fct_grades_term portion). Reads canonical region
through stg_google_sheets__people__locations keyed on the new
_dbt_source_project column from base_powerschool__final_grades."
```

---

### Task 8: Replace regex region join in `bridge_course_section_terms`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/bridges/bridge_course_section_terms.sql`

- [ ] **Step 1: Add `location_regions` CTE and rewrite the join**

Replace the entire contents of `bridge_course_section_terms.sql` with:

```sql
with
    location_regions as (
        select dagster_code_location, location_region,
        from {{ ref("stg_google_sheets__people__locations") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["sec.sections_dcid", "sec._dbt_source_relation"]
        )
    }} as course_section_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,

    rt.academic_year,

from {{ ref("base_powerschool__sections") }} as sec
inner join
    location_regions as lr
    on lr.dagster_code_location = sec._dbt_source_project
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sec.sections_schoolid = rt.school_id
    and rt.type = 'RT'
    and sec.terms_lastday >= rt.start_date
    and sec.terms_firstday <= rt.end_date
    and rt.region = lr.location_region
```

The `term_key` hash inputs are unchanged — both this bridge and `dim_terms` hash
from `rt.region` / `t.region` (raw), so FKs resolve.

- [ ] **Step 2: Build the model and run tests**

```bash
$DBT build --select bridge_course_section_terms --project-dir $DBT_DIR
```

Expected: rebuilds without error; `relationships` tests pass.

- [ ] **Step 3: Verify FK to `dim_terms` resolves**

```sql
select count(*) as n_orphans
from `teamster-332318.kipptaf.bridge_course_section_terms` as b
left join `teamster-332318.kipptaf.dim_terms` as t using (term_key)
where t.term_key is null
```

Expected: 0.

- [ ] **Step 4: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/bridges/bridge_course_section_terms.sql
git -C $WT commit -m "refactor(dbt): replace regex region join in bridge_course_section_terms

Closes #3739 (bridge portion)."
```

---

### Task 9: Add `points_earned` + `numeric_grade_earned` to intermediate

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml`

- [ ] **Step 1: Add the typed columns to the `scores` CTE**

In `int_powerschool__gradebook_assignments_scores.sql`, the existing `scores`
CTE (around lines 47-51) has:

```sql
            if(
                a.scoretype = 'POINTS',
                s.scorepoints,
                safe_cast(s.actualscoreentered as numeric)
            ) as score_entered,
```

Add the two new typed columns immediately after this `score_entered` definition
(insert at line 52, before the existing
`if(... a.scoretype = 'POINTS' ...) as assign_final_score_percent` block):

```sql
            if(a.scoretype = 'POINTS', s.scorepoints, null) as points_earned,

            if(
                a.scoretype in ('PERCENT', 'GRADESCALE', 'COLLECTED'),
                safe_cast(s.actualscoreentered as numeric),
                null
            ) as numeric_grade_earned,
```

Then add the columns to the final SELECT (around line 83-108). Insert between
`score_entered` (line 106) and `assign_final_score_percent` (line 107):

```sql
    points_earned,
    numeric_grade_earned,
```

The legacy `score_entered`, `scoretype`, and downstream `is_zero` / `is_null` /
`is_expected_*` flag columns remain unchanged for tableau-extract consumers.

- [ ] **Step 2: Add the new columns to the properties YAML**

In `int_powerschool__gradebook_assignments_scores.yml`, insert two new entries
immediately after the `score_entered` entry (after line 116):

```yaml
- name: points_earned
  data_type: float64
  description: >-
    Raw points scored, populated only when source `scoretype = POINTS` (NULL for
    PERCENT/GRADESCALE/COLLECTED). Ed-Fi studentGradebookEntry `points_earned`.
  config:
    meta:
      source_system: PowerSchool
      source_model: stg_powerschool__assignmentscore
      source_column: scorepoints
- name: numeric_grade_earned
  data_type: float64
  description: >-
    Numeric grade scored (0-100 percent or letter-grade equivalent), populated
    only when source `scoretype` is `PERCENT`, `GRADESCALE`, or `COLLECTED`
    (NULL for POINTS). Ed-Fi studentGradebookEntry `numeric_grade_earned`.
  config:
    meta:
      source_system: PowerSchool
      source_model: stg_powerschool__assignmentscore
      source_column: actualscoreentered
```

- [ ] **Step 3: Build the model**

```bash
$DBT build --select int_powerschool__gradebook_assignments_scores --project-dir $DBT_DIR --exclude resource_type:test
```

Expected: rebuilds without error.

- [ ] **Step 4: Verify column populations match scoretype distribution**

```sql
select scoretype,
  countif(points_earned is not null) as n_points_earned,
  countif(numeric_grade_earned is not null) as n_numeric_grade_earned,
  count(*) as n
from `teamster-332318.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
group by 1
order by n desc
```

Expected:

- `POINTS`: `n_points_earned` close to `n` (20.3M), `n_numeric_grade_earned`
  = 0.
- `PERCENT`: `n_points_earned` = 0, `n_numeric_grade_earned` close to `n`
  (4.4M).
- `GRADESCALE`: `n_points_earned` = 0, small `n_numeric_grade_earned` (~7).
- `COLLECTED`: `n_points_earned` = 0, small `n_numeric_grade_earned` (~129).

- [ ] **Step 5: Verify legacy `score_entered` still equals
      `coalesce(points_earned, numeric_grade_earned)`**

```sql
select countif(
  coalesce(points_earned, numeric_grade_earned) is distinct from score_entered
) as mismatches
from `teamster-332318.kipptaf_powerschool.int_powerschool__gradebook_assignments_scores`
```

Expected: 0 — the typed columns coalesce back to the legacy value.

- [ ] **Step 6: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__gradebook_assignments_scores.yml
git -C $WT commit -m "refactor(dbt): add Ed-Fi-aligned typed score columns to int gradebook scores

Closes #3688 (intermediate portion). Adds points_earned and
numeric_grade_earned alongside the existing score_entered / scoretype
to expose Ed-Fi gradebookEntry naming. Legacy columns retained for
tableau-extract consumers."
```

---

### Task 10: Update `fct_grades_assignments` — drop `score`/`score_type`, add typed columns

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml`

- [ ] **Step 1: Replace the score columns in the SQL final SELECT**

In `fct_grades_assignments.sql`, replace the two lines at 93-95:

```sql
    asg.assignment_name as `name`,
    asg.category_name,
    asg.category_code,
    asg.scoretype as score_type,

    asg.score_entered as score,
    asg.totalpointvalue as max_points,
    asg.assign_final_score_percent as score_percent,
```

With:

```sql
    asg.assignment_name as `name`,
    asg.category_name,
    asg.category_code,

    asg.points_earned,
    asg.numeric_grade_earned,
    asg.totalpointvalue as max_points,
    asg.assign_final_score_percent as score_percent,
```

- [ ] **Step 2: Replace `score` and `score_type` entries in the properties
      YAML**

In `fct_grades_assignments.yml`, locate the `score_type` block (lines 118-127)
and the `score` block (lines 128-134). Delete both. In their place, insert:

```yaml
- name: points_earned
  data_type: float64
  description: >-
    Raw points the student scored on this assignment. Populated only when the
    source assignment uses `POINTS` scoring (NULL otherwise). Ed-Fi
    studentGradebookEntry `points_earned`.

  config:
    meta:
      source_system: PowerSchool
      source_model: stg_powerschool__assignmentscore
      source_column: scorepoints
- name: numeric_grade_earned
  data_type: float64
  description: >-
    Numeric grade the student earned (0-100 percent or letter-grade equivalent).
    Populated only when the source assignment uses `PERCENT`, `GRADESCALE`, or
    `COLLECTED` scoring (NULL otherwise). Ed-Fi studentGradebookEntry
    `numeric_grade_earned`.

  config:
    meta:
      source_system: PowerSchool
      source_model: stg_powerschool__assignmentscore
      source_column: actualscoreentered
```

- [ ] **Step 3: Build the model and run tests**

```bash
$DBT build --select fct_grades_assignments --project-dir $DBT_DIR
```

Expected: model rebuilds with new columns; contract enforces against the updated
YAML; `relationships` tests on `term_key` pass.

- [ ] **Step 4: Verify mart row count and column population**

```sql
select
  count(*) as total,
  countif(points_earned is not null) as n_points_earned,
  countif(numeric_grade_earned is not null) as n_numeric_grade_earned,
from `teamster-332318.kipptaf.fct_grades_assignments`
```

Expected: total close to 24.9M; `n_points_earned` ≈ 20.3M;
`n_numeric_grade_earned` ≈ 4.6M.

- [ ] **Step 5: Confirm dropped columns absent**

```sql
select column_name
from `teamster-332318.kipptaf.INFORMATION_SCHEMA.COLUMNS`
where table_name = 'fct_grades_assignments'
  and column_name in ('score', 'score_type')
```

Expected: 0 rows.

- [ ] **Step 6: Commit**

```bash
git -C $WT add src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql src/dbt/kipptaf/models/marts/facts/properties/fct_grades_assignments.yml
git -C $WT commit -m "refactor(dbt): expose points_earned/numeric_grade_earned on fct_grades_assignments

Closes #3688 (mart portion). Drops polymorphic score/score_type in
favor of Ed-Fi-aligned typed columns. Cube schema update for the
removed columns is tracked separately (out of dbt scope)."
```

---

### Task 11: Final validation, push, and PR

**Files:** none modified.

- [ ] **Step 1: Rebuild the full affected subgraph**

```bash
$DBT build \
  --select stg_google_sheets__reporting__terms+ stg_powerschool__schools+ \
           base_powerschool__final_grades+ base_powerschool__sections+ \
           int_powerschool__gradebook_assignments_scores+ \
  --project-dir $DBT_DIR
```

Expected: every model rebuilds; every test passes at error severity.

- [ ] **Step 2: Pre-merge checklist (from spec)**

Confirm each:

- Diamond-path scan: no fact in scope gains a new FK to a shared dim. (Verified
  during brainstorming; no new FKs added.)
- Column-naming rubric (R1–R10) on touched mart columns: `points_earned`,
  `numeric_grade_earned`, `max_points`, `score_percent` are R1/R6 compliant;
  `_dbt_source_project` stays plumbing per R8.
- Project-board scan: skim
  https://github.com/orgs/TEAMSchools/projects/4/views/1 for incidentally
  resolved issues; list any in PR body.
- New-issue triage: file any newly surfaced errors as issues with `Tier`,
  `PR batch`, and `Driver` set.

- [ ] **Step 3: Push branch**

```bash
git -C $WT push -u origin cbini/refactor/claude-batch-m-grades-hardening
```

- [ ] **Step 4: Open PR via GitHub MCP**

Use `mcp__github__create_pull_request` with:

- `owner`: `TEAMSchools`
- `repo`: `teamster`
- `head`: `cbini/refactor/claude-batch-m-grades-hardening`
- `base`: `main`
- `title`: `refactor(dbt): batch M grades hardening`
- `body`: copy from the spec's verification + risk sections; include the issue
  list from the spec header (Closes #3677, #3688, #3691, #3738, #3739) and the
  project-board incidentally-resolved bonuses (if any).

- [ ] **Step 5: Link the PR's branch to all 5 issues**

For each of #3677, #3688, #3691, #3738, #3739, link the existing branch to the
issue. Per CLAUDE.md note: `mcp__github__create_branch` no-ops on existing
branches, so we use the post-push linkage path. Since the branch already has
commits, use `gh issue develop` only for issue 1 (after deleting any stale
linked branch first); for issues 2-5, comment on each issue with a link to the
PR — GitHub auto-closes them when the PR merges via `Closes #N` in the PR body.

- [ ] **Step 6: Final dbt Cloud CI check**

After push, monitor the dbt Cloud CI run for the PR. Per `kipptaf/CLAUDE.md`,
the CI job runs `dbt build --select state:modified+ --full-refresh` against
staging, deferring to the Staging environment.

If the CI fails on a stale staging defer table for an unmodified upstream,
trigger the full `Clone - Staging` job per the same CLAUDE.md guidance.

---

## Spec coverage map

| Spec section                                              | Plan task                                                                                |
| --------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Section 1 (Paterson CASE fix)                             | Task 4                                                                                   |
| Section 2 (`dim_terms` regex-region join refactor)        | Task 6                                                                                   |
| Section 3 (RT uniqueness test + warn→error promotion)     | Task 5 + Task 6                                                                          |
| Section 4.1 (`_dbt_source_project` on three union models) | Tasks 1, 2, 3                                                                            |
| Section 4.2 (mart join rewrites)                          | Task 6 (`dim_terms`), Task 7 (`fct_grades_term`), Task 8 (`bridge_course_section_terms`) |
| Section 5.1 (intermediate split)                          | Task 9                                                                                   |
| Section 5.2 (mart fact column split)                      | Task 10                                                                                  |
| Validation queries                                        | Task 11 step 1                                                                           |
| Pre-merge checklist                                       | Task 11 step 2                                                                           |
