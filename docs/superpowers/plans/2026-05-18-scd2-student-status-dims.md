# SCD2 Student-Status Dims Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three SCD2-style mart dimensions (`dim_iep_status`,
`dim_ell_status`, `dim_meal_eligibility_status`) sourced from native
effective-date upstreams for Newark + Camden and current-state PowerSchool for
Paterson + Miami, while promoting `_dbt_source_project` materialization on four
upstream union models.

**Architecture:** Each dim is a single mart-layer model — no intermediates. NJ
leg pulls native effective dates (edplan / `s_nj_stu_x` / Titan) with
island-collapse. Paterson + Miami leg pulls current PowerSchool values anchored
to first observed `entrydate`. PKs hash
`(student_number, _dbt_source_project, effective_date_start)`; FKs go to
`dim_students` and `dim_dates` only.

**Tech Stack:** dbt (BigQuery), Jinja, `dbt_utils.generate_surrogate_key`,
`dbt_utils.deduplicate`, kipptaf project-level `union_dataset_join_clause`
macro.

**Worktree:** `.worktrees/cbini/feat/claude-scd2-student-status-dims` (branch
`cbini/feat/claude-scd2-student-status-dims` linked to #3960). All `git -C` and
`dbt --project-dir` calls target the worktree path.

**Spec:**
[docs/superpowers/specs/2026-05-18-scd2-student-status-dims.md](../specs/2026-05-18-scd2-student-status-dims.md).

---

## Task 1: Materialize `_dbt_source_project` on `int_edplan__njsmart_powerschool_union`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/edplan/intermediate/int_edplan__njsmart_powerschool_union.sql`
- Modify:
  `src/dbt/kipptaf/models/edplan/intermediate/properties/int_edplan__njsmart_powerschool_union.yml`

- [ ] **Step 1: Rewrite the SQL to wrap `union_relations` in a CTE and project
      `_dbt_source_project`.**

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_edplan",
                        "int_edplan__njsmart_powerschool_union",
                    ),
                    source(
                        "kippcamden_edplan",
                        "int_edplan__njsmart_powerschool_union",
                    ),
                ]
            )
        }}
    )

select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
```

- [ ] **Step 2: Add the new column to the properties YAML.** Open
      `properties/int_edplan__njsmart_powerschool_union.yml` and append a
      `_dbt_source_project` entry to the `columns:` list:

```yaml
- name: _dbt_source_project
  description: >-
    Source-project discriminator (e.g. `kippnewark`, `kippcamden`) extracted
    from `_dbt_source_relation`. Materialized at the union point so downstream
    consumers can join and hash on a stable value.
```

Per `src/dbt/CLAUDE.md`, tracking-issue refs like `#3142` MUST NOT appear in
YAML descriptions — put them in an inline SQL comment instead. Update the SQL
`select` to:

```sql
select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
```

- [ ] **Step 3: Parse to verify the model and YAML still load.**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: `Update freshness information for 0 sources` then `Found N models...`
with no parse errors.

- [ ] **Step 4: Build the model and immediate descendants to confirm no
      downstream regression.**

```bash
uv run dbt build --select int_edplan__njsmart_powerschool_union+1 --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: every test PASS or WARN; no ERROR.
`base_powerschool__student_enrollments` should still build (it consumes this
model).

- [ ] **Step 5: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): materialize _dbt_source_project on int_edplan__njsmart_powerschool_union (#3960, refs #3142)"
```

---

## Task 2: Materialize `_dbt_source_project` on `stg_powerschool__s_nj_stu_x`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__s_nj_stu_x.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__s_nj_stu_x.yml`

- [ ] **Step 1: Rewrite the SQL to wrap `union_relations` in a CTE and project
      `_dbt_source_project`.** Replace the current bare
      `{{ dbt_utils.union_relations(...) }}` body with:

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__s_nj_stu_x"),
                    source("kippcamden_powerschool", "stg_powerschool__s_nj_stu_x"),
                    source("kipppaterson_powerschool", "stg_powerschool__s_nj_stu_x"),
                ]
            )
        }}
    )

select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
```

(Preserve the existing source list — Newark, Camden, Paterson — exactly as it
currently is; do not add or remove districts.)

- [ ] **Step 2: Append `_dbt_source_project` to the YAML `columns:` list with
      the same description as Task 1 Step 2.**

- [ ] **Step 3: Parse to verify load.**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: success.

- [ ] **Step 4: Build the model and immediate descendants.**

```bash
uv run dbt build --select stg_powerschool__s_nj_stu_x+1 --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: every test PASS or WARN.

- [ ] **Step 5: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): materialize _dbt_source_project on stg_powerschool__s_nj_stu_x (#3960, refs #3142)"
```

---

## Task 3: Materialize `_dbt_source_project` on `stg_titan__person_data`

**Files:**

- Modify: `src/dbt/kipptaf/models/titan/staging/stg_titan__person_data.sql`
- Modify:
  `src/dbt/kipptaf/models/titan/staging/properties/stg_titan__person_data.yml`

- [ ] **Step 1: Rewrite the SQL.** Apply the same CTE-wrap pattern from Task 2,
      preserving the existing Newark + Camden source list verbatim:

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_titan", "stg_titan__person_data"),
                    source("kippcamden_titan", "stg_titan__person_data"),
                ]
            )
        }}
    )

select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
```

- [ ] **Step 2: Append `_dbt_source_project` to the YAML.**

- [ ] **Step 3: Parse.**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

- [ ] **Step 4: Build and immediate descendants.**

```bash
uv run dbt build --select stg_titan__person_data+1 --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

- [ ] **Step 5: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): materialize _dbt_source_project on stg_titan__person_data (#3960, refs #3142)"
```

---

## Task 4: Materialize `_dbt_source_project` on `stg_powerschool__studentcorefields`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__studentcorefields.sql`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__studentcorefields.yml`

- [ ] **Step 1: Rewrite the SQL.** Apply the CTE-wrap pattern from Task 2,
      preserving the existing four-district source list:

```sql
with
    unioned as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", "stg_powerschool__studentcorefields"),
                    source("kippcamden_powerschool", "stg_powerschool__studentcorefields"),
                    source("kippmiami_powerschool", "stg_powerschool__studentcorefields"),
                    source("kipppaterson_powerschool", "stg_powerschool__studentcorefields"),
                ]
            )
        }}
    )

select
    *,
    -- materialized source-project discriminator for downstream surrogate-key
    -- composition; replaces per-consumer regexp_extract() per #3142.
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from unioned
```

- [ ] **Step 2: Append `_dbt_source_project` to the YAML.**

- [ ] **Step 3: Parse.**

- [ ] **Step 4: Build and immediate descendants.**

```bash
uv run dbt build --select stg_powerschool__studentcorefields+1 --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

- [ ] **Step 5: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): materialize _dbt_source_project on stg_powerschool__studentcorefields (#3960, refs #3142)"
```

---

## Task 5: Verify `dim_dates` covers `9999-12-31`

**Files:** read-only check.

- [ ] **Step 1: Read `dim_dates.sql` to confirm the date spine includes 9999.**
      Open `src/dbt/kipptaf/models/marts/dimensions/dim_dates.sql` and verify
      line 6 reads:

```sql
from unnest(generate_array(2000, 9999)) as yr
```

If the upper bound is anything less than `9999`, stop and flag — the spec
assumes a sentinel row exists. The current code does generate 9999 dates, so no
model change is needed.

No commit — read-only verification.

---

## Task 6: Build `dim_iep_status`

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_iep_status.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_iep_status.yml`
- Create: `src/dbt/kipptaf/tests/dim_iep_status__no_overlapping_spans.sql`

- [ ] **Step 1: Write the properties YAML first (failing-tests-first).**

```yaml
models:
  - name: dim_iep_status
    description: >-
      SCD2 dimension capturing IEP (special-education) status spans per student.
      One row per student per contiguous value span; active rows end at
      `'9999-12-31'`. Newark + Camden draw from EdPlan with native effective
      dates; Paterson + Miami carry a single current-state span anchored to the
      student's earliest enrollment.
    config:
      meta:
        dagster:
          group: marts
          asset_key:
            - kipptaf
            - marts
            - dim_iep_status
    constraints:
      - type: primary_key
        columns: [iep_status_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [student_key]
        expression: ref('dim_students')
        to_columns: [student_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_start_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_end_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
    columns:
      - name: iep_status_key
        data_type: string
        description: Surrogate primary key.
        data_tests:
          - unique
          - not_null
      - name: student_key
        data_type: string
        description: Foreign key to `dim_students.student_key`.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_students')
                field: student_key
      - name: effective_date_start_key
        data_type: date
        description: First date this span is valid for the student.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: effective_date_end_key
        data_type: date
        description: >-
          Last date this span is valid (inclusive); `'9999-12-31'` for the
          currently-active span.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: is_current
        data_type: boolean
        description: >-
          Convenience flag — true when `effective_date_end_key = '9999-12-31'`.
        data_tests:
          - not_null
      - name: is_iep
        data_type: boolean
        description: >-
          True when the student has an active IEP for this span — derived as
          `iep_classification != 'No IEP'`.
        data_tests:
          - not_null
      - name: _dbt_source_project
        data_type: string
        description: >-
          Source-project discriminator (e.g. `kippnewark`, `kippcamden`,
          `kippmiami`, `kipppaterson`) — required because students may move
          between districts and have parallel status spans per source.
      - name: iep_classification
        data_type: string
        description: >-
          Special-education program classification (e.g. `Resource Center`,
          `In-Class Resource`, `Self-Contained`, `No IEP`). Renamed from the
          source-system field `spedlep`.
      - name: special_education_code
        data_type: string
        description: >-
          NJ state special-education code (e.g. `AU`, `ED`). Populated only for
          Newark + Camden via EdPlan; null for Paterson + Miami.
      - name: special_education_name
        data_type: string
        description: >-
          Descriptive name paired with `special_education_code`. Populated only
          for Newark + Camden via EdPlan; null for Paterson + Miami.
      - name: special_education_placement
        data_type: string
        description: >-
          NJ state special-education placement category. Populated only for
          Newark + Camden via EdPlan; null for Paterson + Miami.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_key
              - _dbt_source_project
              - effective_date_start_key
```

- [ ] **Step 2: Write the singular test for overlapping spans.**

Create `src/dbt/kipptaf/tests/dim_iep_status__no_overlapping_spans.sql`:

```sql
{{
    config(
        meta={
            "dagster": {
                "ref": {"name": "dim_iep_status", "package": "kipptaf"},
            }
        }
    )
}}

with
    spans as (
        select
            student_key,
            effective_date_start_key,
            effective_date_end_key,
            lead(effective_date_start_key) over (
                partition by student_key, _dbt_source_project
                order by effective_date_start_key
            ) as next_start,
        from {{ ref("dim_iep_status") }}
    )

select student_key, effective_date_start_key, effective_date_end_key, next_start,
from spans
where next_start is not null and next_start <= effective_date_end_key
```

- [ ] **Step 3: Run `dbt parse` to verify the YAML and test parse.** Expected:
      parse succeeds; the SQL model `dim_iep_status` is registered but does not
      yet exist.

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

- [ ] **Step 4: Run the contract check to confirm the model is required.**
      Expected: FAIL with "model 'dim_iep_status' not found" or similar —
      confirms YAML loads but SQL is missing.

```bash
uv run dbt build --select dim_iep_status --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected output: model fails to compile because file is absent. This is the
"failing test" — proceed to implementation.

- [ ] **Step 5: Write the model SQL.**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_iep_status.sql`:

```sql
with
    nj_unioned as (
        select
            student_number,
            _dbt_source_project,
            -- edplan ships ~24% NULL spedlep; coalesce to 'No IEP' matches the
            -- base_powerschool__student_enrollments pattern and lets is_iep
            -- resolve to a non-null boolean for every row.
            coalesce(spedlep, 'No IEP') as spedlep,
            special_education_code,
            special_education,
            cast(nj_se_placement as string) as nj_se_placement,
            effective_date,
            effective_end_date,
        from {{ ref("int_edplan__njsmart_powerschool_union") }}
    ),

    nj_flagged as (
        select
            *,
            if(
                format(
                    '%T|%T|%T|%T',
                    spedlep,
                    special_education_code,
                    special_education,
                    nj_se_placement
                )
                = lag(
                    format(
                        '%T|%T|%T|%T',
                        spedlep,
                        special_education_code,
                        special_education,
                        nj_se_placement
                    )
                ) over (
                    partition by student_number, _dbt_source_project
                    order by effective_date
                ),
                0,
                1
            ) as is_island_start,
        from nj_unioned
    ),

    nj_islanded as (
        select
            *,
            sum(is_island_start) over (
                partition by student_number, _dbt_source_project
                order by effective_date
            ) as island_id,
        from nj_flagged
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            spedlep as iep_classification,
            special_education_code,
            special_education as special_education_name,
            nj_se_placement as special_education_placement,
            min(effective_date) as effective_date_start,
            coalesce(
                max(effective_end_date), date '9999-12-31'
            ) as effective_date_end,
        from nj_islanded
        group by
            student_number,
            _dbt_source_project,
            spedlep,
            special_education_code,
            special_education,
            nj_se_placement,
            island_id
    ),

    pm_leg as (
        select
            enr.student_number,
            enr._dbt_source_project,
            coalesce(scf.spedlep, 'No IEP') as iep_classification,
            cast(null as string) as special_education_code,
            cast(null as string) as special_education_name,
            cast(null as string) as special_education_placement,
            min(enr.entrydate) as effective_date_start,
            date '9999-12-31' as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(
                left_alias="enr", right_alias="scf"
            ) }}
        where enr.region in ('Paterson', 'Miami')
        group by
            enr.student_number,
            enr._dbt_source_project,
            coalesce(scf.spedlep, 'No IEP')
    ),

    unioned as (
        select * from nj_leg
        union all
        select * from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as iep_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,
    iep_classification,
    special_education_code,
    special_education_name,
    special_education_placement,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    iep_classification != 'No IEP' as is_iep,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
```

(Note: `_dbt_source_project` is listed in the SELECT so the model-level
uniqueness test on
`(student_key, _dbt_source_project, effective_date_start_key)` resolves. Add it
to the YAML `columns:` list with `data_type: string` and a description like
"Source-project discriminator (see Task 1).")

- [ ] **Step 6: Run the build with tests.**

```bash
uv run dbt build --select dim_iep_status --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: model builds; all tests (`unique`, `not_null`, `relationships` × 3,
`dbt_utils.unique_combination_of_columns`,
`dim_iep_status__no_overlapping_spans`) PASS.

- [ ] **Step 7: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add src/dbt/kipptaf/models/marts/dimensions/dim_iep_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_iep_status.yml src/dbt/kipptaf/tests/dim_iep_status__no_overlapping_spans.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): add dim_iep_status SCD2 mart (#3960)"
```

---

## Task 7: Build `dim_ell_status`

**Files:**

- Create: `src/dbt/kipptaf/models/marts/dimensions/dim_ell_status.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_ell_status.yml`
- Create: `src/dbt/kipptaf/tests/dim_ell_status__no_overlapping_spans.sql`

- [ ] **Step 1: Write the properties YAML.**

```yaml
models:
  - name: dim_ell_status
    description: >-
      SCD2 dimension capturing ELL (English Language Learner) status spans per
      student. Newark + Camden + Paterson draw from PowerSchool `s_nj_stu_x` LEP
      date columns; Miami carries a single current-state span anchored to the
      student's earliest enrollment. Source is current-state — historical
      entry/exit/re-entry transitions that have been overwritten in PowerSchool
      are not recoverable.
    config:
      meta:
        dagster:
          group: marts
          asset_key:
            - kipptaf
            - marts
            - dim_ell_status
    constraints:
      - type: primary_key
        columns: [ell_status_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [student_key]
        expression: ref('dim_students')
        to_columns: [student_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_start_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_end_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
    columns:
      - name: ell_status_key
        data_type: string
        description: Surrogate primary key.
        data_tests:
          - unique
          - not_null
      - name: student_key
        data_type: string
        description: Foreign key to `dim_students.student_key`.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_students')
                field: student_key
      - name: effective_date_start_key
        data_type: date
        description: First date this span is valid for the student.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: effective_date_end_key
        data_type: date
        description: >-
          Last date this span is valid (inclusive); `'9999-12-31'` for the
          currently-active span.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: is_current
        data_type: boolean
        description: True when `effective_date_end_key = '9999-12-31'`.
        data_tests:
          - not_null
      - name: is_ell
        data_type: boolean
        description: True when the student is classified ELL for this span.
        data_tests:
          - not_null
      - name: _dbt_source_project
        data_type: string
        description: Source-project discriminator (see Task 1).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_key
              - _dbt_source_project
              - effective_date_start_key
```

- [ ] **Step 2: Write the singular overlap test.**

Create `src/dbt/kipptaf/tests/dim_ell_status__no_overlapping_spans.sql`:

```sql
{{
    config(
        meta={
            "dagster": {
                "ref": {"name": "dim_ell_status", "package": "kipptaf"},
            }
        }
    )
}}

with
    spans as (
        select
            student_key,
            effective_date_start_key,
            effective_date_end_key,
            lead(effective_date_start_key) over (
                partition by student_key, _dbt_source_project
                order by effective_date_start_key
            ) as next_start,
        from {{ ref("dim_ell_status") }}
    )

select student_key, effective_date_start_key, effective_date_end_key, next_start,
from spans
where next_start is not null and next_start <= effective_date_end_key
```

- [ ] **Step 3: Parse and confirm the model is registered.**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

- [ ] **Step 4: Write the model SQL.**

Create `src/dbt/kipptaf/models/marts/dimensions/dim_ell_status.sql`:

```sql
with
    nj_primary as (
        select
            student_number,
            _dbt_source_project,
            lepbegindate as effective_date_start,
            coalesce(lependdate, date '9999-12-31') as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }}
        where lepbegindate is not null
    ),

    nj_secondary as (
        select
            student_number,
            _dbt_source_project,
            lepbegindate2 as effective_date_start,
            coalesce(liependdate2, date '9999-12-31') as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }}
        where lepbegindate2 is not null
    ),

    nj_leg as (
        select * from nj_primary
        union all
        select * from nj_secondary
    ),

    pm_leg as (
        select
            enr.student_number,
            enr._dbt_source_project,
            min(enr.entrydate) as effective_date_start,
            date '9999-12-31' as effective_date_end,
        from {{ ref("base_powerschool__student_enrollments") }} as enr
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on enr.students_dcid = scf.studentsdcid
            and {{ union_dataset_join_clause(
                left_alias="enr", right_alias="scf"
            ) }}
        where enr.region in ('Paterson', 'Miami')
            and scf.lep_status is true
        group by enr.student_number, enr._dbt_source_project
    ),

    unioned as (
        select * from nj_leg
        union all
        select * from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as ell_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    true as is_ell,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
```

(`is_ell` is always `true` because the dim is inclusion-based — consumers
default to `false` when no row covers the target date, per the spec's
row-semantics section.)

- [ ] **Step 5: Build with tests.**

```bash
uv run dbt build --select dim_ell_status --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: PASS / WARN, no ERROR.

- [ ] **Step 6: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add src/dbt/kipptaf/models/marts/dimensions/dim_ell_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_ell_status.yml src/dbt/kipptaf/tests/dim_ell_status__no_overlapping_spans.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): add dim_ell_status SCD2 mart (#3960)"
```

---

## Task 8: Build `dim_meal_eligibility_status`

**Files:**

- Create:
  `src/dbt/kipptaf/models/marts/dimensions/dim_meal_eligibility_status.sql`
- Create:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_meal_eligibility_status.yml`
- Create:
  `src/dbt/kipptaf/tests/dim_meal_eligibility_status__no_overlapping_spans.sql`

- [ ] **Step 1: Write the properties YAML.**

```yaml
models:
  - name: dim_meal_eligibility_status
    description: >-
      SCD2 dimension capturing meal-eligibility (NSLP) status spans per student.
      Newark + Camden draw from Titan with native effective dates; Paterson +
      Miami carry a single current-state span using the most recent
      `lunch_status` value from enrollment, anchored to the student's earliest
      enrollment.
    config:
      meta:
        dagster:
          group: marts
          asset_key:
            - kipptaf
            - marts
            - dim_meal_eligibility_status
    constraints:
      - type: primary_key
        columns: [meal_eligibility_status_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [student_key]
        expression: ref('dim_students')
        to_columns: [student_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_start_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
      - type: foreign_key
        columns: [effective_date_end_key]
        expression: ref('dim_dates')
        to_columns: [date_key]
        warn_unsupported: false
    columns:
      - name: meal_eligibility_status_key
        data_type: string
        description: Surrogate primary key.
        data_tests:
          - unique
          - not_null
      - name: student_key
        data_type: string
        description: Foreign key to `dim_students.student_key`.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_students')
                field: student_key
      - name: effective_date_start_key
        data_type: date
        description: First date this span is valid for the student.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: effective_date_end_key
        data_type: date
        description: >-
          Last date this span is valid (inclusive); `'9999-12-31'` for the
          currently-active span.
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_dates')
                field: date_key
      - name: is_current
        data_type: boolean
        description: True when `effective_date_end_key = '9999-12-31'`.
        data_tests:
          - not_null
      - name: is_meal_eligible
        data_type: boolean
        description: >-
          True when `meal_eligibility` is `Free`, `Reduced`, or `Direct
          Certification`. Paid / null / invalid codes resolve to false.
        data_tests:
          - not_null
      - name: meal_eligibility
        data_type: string
        description: >-
          Meal-eligibility classification. Titan source values for Newark +
          Camden; raw `lunch_status` from PowerSchool for Paterson + Miami.
      - name: _dbt_source_project
        data_type: string
        description: Source-project discriminator (see Task 1).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - student_key
              - _dbt_source_project
              - effective_date_start_key
```

- [ ] **Step 2: Write the singular overlap test.**

Create
`src/dbt/kipptaf/tests/dim_meal_eligibility_status__no_overlapping_spans.sql`:

```sql
{{
    config(
        meta={
            "dagster": {
                "ref": {"name": "dim_meal_eligibility_status", "package": "kipptaf"},
            }
        }
    )
}}

with
    spans as (
        select
            student_key,
            effective_date_start_key,
            effective_date_end_key,
            lead(effective_date_start_key) over (
                partition by student_key, _dbt_source_project
                order by effective_date_start_key
            ) as next_start,
        from {{ ref("dim_meal_eligibility_status") }}
    )

select student_key, effective_date_start_key, effective_date_end_key, next_start,
from spans
where next_start is not null and next_start <= effective_date_end_key
```

- [ ] **Step 3: Parse.**

- [ ] **Step 4: Write the model SQL.**

Create
`src/dbt/kipptaf/models/marts/dimensions/dim_meal_eligibility_status.sql`:

```sql
with
    nj_unioned as (
        select
            student_number,
            _dbt_source_project,
            eligibility_name,
            eligibility_start_date,
            eligibility_end_date,
        from {{ ref("stg_titan__person_data") }}
        where eligibility_start_date is not null
    ),

    nj_flagged as (
        select
            *,
            if(
                eligibility_name = lag(eligibility_name) over (
                    partition by student_number, _dbt_source_project
                    order by eligibility_start_date
                ),
                0,
                1
            ) as is_island_start,
        from nj_unioned
    ),

    nj_islanded as (
        select
            *,
            sum(is_island_start) over (
                partition by student_number, _dbt_source_project
                order by eligibility_start_date
            ) as island_id,
        from nj_flagged
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            eligibility_name as meal_eligibility,
            min(eligibility_start_date) as effective_date_start,
            coalesce(
                max(eligibility_end_date), date '9999-12-31'
            ) as effective_date_end,
        from nj_islanded
        group by student_number, _dbt_source_project, eligibility_name, island_id
    ),

    pm_recent as (
        {{
            dbt_utils.deduplicate(
                relation=ref("base_powerschool__student_enrollments"),
                partition_by="student_number, _dbt_source_project",
                order_by="entrydate desc",
            )
        }}
    ),

    pm_leg as (
        select
            r.student_number,
            r._dbt_source_project,
            r.lunch_status as meal_eligibility,
            anchor.effective_date_start,
            date '9999-12-31' as effective_date_end,
        from pm_recent as r
        inner join
            (
                select
                    student_number,
                    _dbt_source_project,
                    min(entrydate) as effective_date_start,
                from {{ ref("base_powerschool__student_enrollments") }}
                where region in ('Paterson', 'Miami')
                group by student_number, _dbt_source_project
            ) as anchor
            on r.student_number = anchor.student_number
            and r._dbt_source_project = anchor._dbt_source_project
        where r.region in ('Paterson', 'Miami')
    ),

    unioned as (
        select * from nj_leg
        union all
        select * from pm_leg
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as meal_eligibility_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    _dbt_source_project,
    meal_eligibility,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    meal_eligibility in ('Free', 'Reduced', 'Direct Certification') as is_meal_eligible,
    effective_date_end = date '9999-12-31' as is_current,
from unioned
```

- [ ] **Step 5: Build with tests.**

```bash
uv run dbt build --select dim_meal_eligibility_status --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: PASS / WARN.

- [ ] **Step 6: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add src/dbt/kipptaf/models/marts/dimensions/dim_meal_eligibility_status.sql src/dbt/kipptaf/models/marts/dimensions/properties/dim_meal_eligibility_status.yml src/dbt/kipptaf/tests/dim_meal_eligibility_status__no_overlapping_spans.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): add dim_meal_eligibility_status SCD2 mart (#3960)"
```

---

## Task 9: Remove `is_ell` from `dim_students`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_students.sql`
- Modify: `src/dbt/kipptaf/models/marts/dimensions/properties/dim_students.yml`

- [ ] **Step 1: Edit `dim_students.sql`.** Remove the line that emits `is_ell`:

```sql
scf.lep_status as is_ell,
```

Also remove the `stg_powerschool__studentcorefields` LEFT JOIN if it's no longer
referenced after dropping that line. (Inspect the file — it currently joins
`scf` solely for `lep_status`. Remove the join only if no other column from
`scf` is used; otherwise leave it.)

- [ ] **Step 2: Edit `dim_students.yml`.** Delete the `is_ell` column block
      (currently around line 126 — search for `- name: is_ell`).

- [ ] **Step 3: Parse and build `dim_students` plus its descendants.**

```bash
uv run dbt build --select dim_students+ --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: model builds; no contract violation; downstream tests still PASS (no
current mart consumer reads `is_ell` from `dim_students` per the spec's
prerelease posture).

- [ ] **Step 4: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "refactor(dbt/kipptaf): drop is_ell from dim_students; use dim_ell_status (#3960)"
```

---

## Task 10: Add the three new dims to `cube.yml` `cube_semantic_layer.depends_on`

**Files:**

- Modify: `src/dbt/kipptaf/models/exposures/cube.yml`

- [ ] **Step 1: Open `cube.yml` and locate the `cube_semantic_layer` exposure's
      `depends_on` list.** It should already contain entries like
      `ref('dim_students')`. Add three new entries (alphabetized within the dim
      block):

```yaml
- ref('dim_ell_status')
- ref('dim_iep_status')
- ref('dim_meal_eligibility_status')
```

- [ ] **Step 2: Parse to verify the exposure resolves.**

```bash
uv run dbt parse --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: success.

- [ ] **Step 3: Commit.**

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims add -u
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims commit -m "feat(dbt/kipptaf): add status-dim refs to cube_semantic_layer exposure (#3960)"
```

---

## Task 11: Full-lineage verification build

**Files:** none modified.

- [ ] **Step 1: Build the three new dims plus their full upstream/downstream
      slice.**

```bash
uv run dbt build \
  --select +dim_iep_status +dim_ell_status +dim_meal_eligibility_status dim_students+ \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf
```

Expected: every model builds; every test PASS or WARN; zero ERROR. Mart
contracts validate column types and nullability.

- [ ] **Step 2: Scan `logs/dbt.log` for any singular-test failures, contract
      drift, or relationships warnings.**

```bash
grep -nE 'FAIL|ERROR|severity=error' /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims/src/dbt/kipptaf/logs/dbt.log | tail -50
```

Expected: only entries pre-dating this run; no new failures.

- [ ] **Step 3: Confirm trunk lint clean before push.**

```bash
.trunk/tools/trunk check --force \
  src/dbt/kipptaf/models/marts/dimensions/dim_iep_status.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_ell_status.sql \
  src/dbt/kipptaf/models/marts/dimensions/dim_meal_eligibility_status.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_iep_status.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_ell_status.yml \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_meal_eligibility_status.yml \
  src/dbt/kipptaf/tests/dim_iep_status__no_overlapping_spans.sql \
  src/dbt/kipptaf/tests/dim_ell_status__no_overlapping_spans.sql \
  src/dbt/kipptaf/tests/dim_meal_eligibility_status__no_overlapping_spans.sql
```

Expected: `No issues`.

- [ ] **Step 4: Run the spec's pre-merge checklist (per the spec's Pre-merge
      checks section).** Diamond-path scan, naming rubric audit (R1–R10),
      confirm cube depends_on lists all three dims, pull CI warnings via
      `mcp__dbt__get_job_run_error(warning_only=true)` once a CI run exists for
      the PR branch, scan project board #4 for incidentally-resolved issues.

- [ ] **Step 5: Open the PR.** Push the branch:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-scd2-student-status-dims push -u origin cbini/feat/claude-scd2-student-status-dims
```

Then create the PR using `.github/pull_request_template.md` as the body,
referencing #3960.
