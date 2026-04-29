# Batch D — Staff Observation FK Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate ~273K orphan FKs on staff observation rubric/measurement
dims, add the missing observation-type FK to
`dim_staff_observation_expectations`, centralize the duplicated SchoolMint Grow
observation-type lookup into a single intermediate, and promote the rubric-key
relationships test to error severity now that orphans resolve.

**Closes:** #3641, #3680, #3712, #3722.

**Architecture:** Two-front fix. (1) Remove `_dagster_partition_key = 'f'`
filters from two Grow staging models so archived rubrics/measurements appear in
their dims, eliminating all rubric/measurement FK orphans. (2) Build a new
`int_schoolmint_grow__observation_types` intermediate that pre-hashes
`staff_observation_type_key` from Grow generic_tags; rewire
`dim_staff_observation_types`, `int_schoolmint_grow__observations`, and
`dim_staff_observation_expectations` to consume it. Pre-hash `term_key` and
`staff_observation_rubric_key` upstream too, removing dead defensive `if()`
wrappers and a no-op `row_number` dedup from `fct_staff_observations`.

**Tech Stack:** dbt-core 1.11+, BigQuery, dbt_utils. Project:
`src/dbt/kipptaf/`. All commands run via
`uv run dbt <cmd> --project-dir=src/dbt/kipptaf/`.

**Spec:**
[docs/superpowers/specs/2026-04-29-batch-d-staff-observation-fks-design.md](../specs/2026-04-29-batch-d-staff-observation-fks-design.md).

**Branch:** `cbini/fix/claude-batch-d-staff-observation-fks` (already created).

---

## File Map

### Created

- `src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observation_types.sql`
- `src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observation_types.yml`

### Modified

- `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__rubrics__measurement_groups__measurements.sql`
  — drop partition filter
- `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__measurements.sql`
  — drop partition filter
- `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml`
  — describe convention deviation
- `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__measurements.yml`
  — describe convention deviation
- `src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_types.sql` —
  ref new intermediate
- `src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql`
  — left-join new intermediate; pre-hash rubric_key
- `src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml`
  — uniqueness, not_null tests, new columns
- `src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__observations.sql`
  — pre-hash term_key in both UNION branches
- `src/dbt/kipptaf/models/performance_management/intermediate/properties/int_performance_management__observations.yml`
  — close TODO with unique test, add `term_key` column
- `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql` — drop inline
  CTE/joins/wrappers/dedup; consume pre-hashed keys
- `src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_expectations.sql`
  — add `staff_observation_type_key` FK
- `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_observation_expectations.yml`
  — new column with relationships test

---

## Working conventions

- All `git add` commands name specific files explicitly (no `-A`/`-u`/`.`).
- All commit messages use
  [conventional commits](https://www.conventionalcommits.org/) (`fix(dbt): ...`,
  `refactor(dbt): ...`, `test(dbt): ...`).
- Trunk format runs as a PostToolUse hook on Edit/Write — do not run `trunk fmt`
  manually.
- Before pushing, run `/workspaces/teamster/.trunk/tools/trunk check --ci` from
  the repo root.
- dbt MCP `mcp__dbt__show` is available for ad-hoc compiled-SQL inspection
  during the work; BigQuery MCP for verifying counts.

---

## Task 1 — Remove archived-partition filters from rubric/measurement staging

**Files:**

- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__rubrics__measurement_groups__measurements.sql`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__measurements.sql`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__measurements.yml`

- [ ] **Step 1.1: Drop the `_dagster_partition_key = 'f'` filter from the rubric
      staging model.**

Open
`src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__rubrics__measurement_groups__measurements.sql`.
Delete the final line:

```sql
where r._dagster_partition_key = 'f'
```

The model should end at `left join unnest(mg.measurements) as m`.

- [ ] **Step 1.2: Drop the `_dagster_partition_key = 'f'` filter from the
      measurement staging model.**

Open
`src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__measurements.sql`.
Delete the final line:

```sql
where _dagster_partition_key = 'f'
```

- [ ] **Step 1.3: Document the convention deviation on the rubric staging
      properties file.**

Open
`src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml`.
Add a top-level `description:` to the model (under `name:`). Insert before
`columns:`:

```yaml
description: >-
  Flattened view of SchoolMint Grow rubrics with their nested measurement groups
  and measurements. Includes both archived and non-archived rubrics (deviates
  from the project-wide `_dagster_partition_key = 'f'` convention) so that
  downstream observation facts can resolve historical rubric references. Filter
  on `archived_at` if non-archived rows are needed.
```

- [ ] **Step 1.4: Document the convention deviation on the measurement staging
      properties file.**

Open
`src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__measurements.yml`.
Insert before `columns:`:

```yaml
description: >-
  SchoolMint Grow measurement metadata. Includes both archived and non-archived
  measurements (deviates from the project-wide `_dagster_partition_key = 'f'`
  convention) so that downstream observation score facts can resolve historical
  measurement references. Filter on `archived_at` if non-archived rows are
  needed.
```

- [ ] **Step 1.5: Build and test the two staging models.**

```bash
cd /workspaces/teamster
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select stg_schoolmint_grow__rubrics__measurement_groups__measurements stg_schoolmint_grow__measurements
```

Expected: both models build, all tests pass (existing `unique` test on
`measurement_id` still holds because `dbt_utils.deduplicate` partitions by id).

- [ ] **Step 1.6: Verify archived rows are now present.**

Use BigQuery MCP `mcp__bigquery__execute_sql`:

```sql
select
  countif(archived_at is null) as non_archived,
  countif(archived_at is not null) as archived,
  count(*) as total,
from `teamster-332318.{{ dev_schema }}.stg_schoolmint_grow__measurements`
```

Replace `{{ dev_schema }}` with the actual dev schema (typically
`<github_user>_kipptaf_schoolmint_grow`). Expected: `archived` > 0 (specifically
should include the 348 archived measurements).

Same query against
`stg_schoolmint_grow__rubrics__measurement_groups__measurements` — expected
`archived` rows present.

- [ ] **Step 1.7: Commit.**

```bash
git add src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__rubrics__measurement_groups__measurements.sql \
        src/dbt/kipptaf/models/schoolmint/grow/staging/stg_schoolmint_grow__measurements.sql \
        src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__rubrics__measurement_groups__measurements.yml \
        src/dbt/kipptaf/models/schoolmint/grow/staging/properties/stg_schoolmint_grow__measurements.yml
git commit -m "fix(dbt): expose archived rubrics/measurements in Grow staging (#3722)

Drops the _dagster_partition_key = 'f' filter from
stg_schoolmint_grow__rubrics__measurement_groups__measurements and
stg_schoolmint_grow__measurements. The archived 't' partitions hold
75 rubrics and 348 measurements still referenced by published 2024+
observations. Non-archived consumers can filter on archived_at."
```

---

## Task 2 — Create `int_schoolmint_grow__observation_types` intermediate

**Files:**

- Create:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observation_types.sql`
- Create:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observation_types.yml`

- [ ] **Step 2.1: Create the SQL file.**

Write
`src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observation_types.sql`:

```sql
select
    {{ dbt_utils.generate_surrogate_key(["tag_id"]) }} as staff_observation_type_key,
    tag_id,
    abbreviation,
    `name`,
from {{ ref("stg_schoolmint_grow__generic_tags") }}
where tag_type = 'observationtypes' and archived_at is null
```

- [ ] **Step 2.2: Create the properties YAML.**

Write
`src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observation_types.yml`:

```yaml
models:
  - name: int_schoolmint_grow__observation_types
    description: >-
      Observation type lookup. One row per non-archived SchoolMint Grow generic
      tag where tag_type = 'observationtypes'. Single source of truth for the
      abbreviation → tag_id → staff_observation_type_key mapping consumed by
      dim_staff_observation_types, int_schoolmint_grow__observations, and
      dim_staff_observation_expectations.
    columns:
      - name: staff_observation_type_key
        data_type: string
        description: >-
          Surrogate key derived from tag_id. Generated with
          generate_surrogate_key(["tag_id"]).
        data_tests:
          - unique
          - not_null
      - name: tag_id
        data_type: string
        description: >-
          SchoolMint Grow generic tag identifier for the observation type.
        data_tests:
          - unique
          - not_null
      - name: abbreviation
        data_type: string
        description: >-
          Short code for the observation type (e.g. WT, O3, PMS, PMC, TR). Joins
          to reporting term `type` codes 1:1.
        data_tests:
          - unique
          - not_null
      - name: name
        quote: true
        data_type: string
        description: >-
          Full display name of the observation type (e.g. Walkthrough,
          One-on-One, PM Semester).
```

- [ ] **Step 2.3: Build the new intermediate.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select int_schoolmint_grow__observation_types
```

Expected: model builds, all 4 tests pass (`unique` and `not_null` on
`tag_id`/`abbreviation` plus `unique`/`not_null` on the surrogate key).

- [ ] **Step 2.4: Commit.**

```bash
git add src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observation_types.sql \
        src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observation_types.yml
git commit -m "feat(dbt): add int_schoolmint_grow__observation_types lookup (#3680)

Centralizes the SchoolMint Grow observation-type filter and surrogate
key derivation. Pre-hashes staff_observation_type_key so downstream
consumers (dim_staff_observation_types,
int_schoolmint_grow__observations,
dim_staff_observation_expectations) can pull the key directly without
duplicating the filter or hash logic."
```

---

## Task 3 — Refactor `dim_staff_observation_types` to consume the new intermediate

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_types.sql`

- [ ] **Step 3.1: Replace the SQL with a passthrough from the intermediate.**

Replace the entire contents of
`src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_types.sql` with:

```sql
select
    staff_observation_type_key,
    `name`,
    abbreviation,
from {{ ref("int_schoolmint_grow__observation_types") }}
```

- [ ] **Step 3.2: Build and test.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select dim_staff_observation_types
```

Expected: model builds, all existing tests pass (`unique`, `not_null` on
`staff_observation_type_key`).

- [ ] **Step 3.3: Verify hash values unchanged.**

Use BigQuery MCP to compare hashes against production:

```sql
with
    pr_branch as (
        select staff_observation_type_key, abbreviation
        from `teamster-332318.{{ dev_schema }}.dim_staff_observation_types`
    ),
    prod as (
        select staff_observation_type_key, abbreviation
        from `teamster-332318.kipptaf.dim_staff_observation_types`
    )
select count(*) as total_rows,
    countif(p.staff_observation_type_key = pr.staff_observation_type_key) as matching_keys
from prod as p
inner join pr_branch as pr using (abbreviation)
```

Expected: `total_rows = matching_keys` (every abbreviation hashes to the same
key as production).

- [ ] **Step 3.4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_types.sql
git commit -m "refactor(dbt): dim_staff_observation_types reads from int lookup (#3680)

Consumes int_schoolmint_grow__observation_types instead of duplicating
the tag_type filter and inline surrogate-key hash. Hash values
unchanged; same composition (['tag_id']), same source rows."
```

---

## Task 4 — Refactor `int_schoolmint_grow__observations` to expose pre-hashed FK keys

**Files:**

- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql`
- Modify:
  `src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml`

- [ ] **Step 4.1: Add the FK-key columns and the new join.**

Replace the entire contents of
`src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql`
with:

```sql
select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.score,
    o.list_two_column_a_str as glows,
    o.list_two_column_b_str as grows,
    o.locked,
    o.observed_at,
    o.observed_at_date_local,
    o.academic_year,
    o.is_published,
    o.magic_notes_text,

    s.name as school_name,

    ot.staff_observation_type_key,
    ot.name as observation_type_name,
    ot.abbreviation as observation_type_abbreviation,

    gt2.name as observation_course,

    gt3.name as observation_grade,

    loc.location_key,

    safe_cast(ut.internal_id as int) as teacher_internal_id,

    safe_cast(uo.internal_id as int) as observer_internal_id,

    {{ dbt_utils.generate_surrogate_key(["o.rubric_id"]) }}
    as staff_observation_rubric_key,
from {{ ref("stg_schoolmint_grow__observations") }} as o
left join {{ ref("stg_schoolmint_grow__users") }} as ut on o.teacher_id = ut.user_id
left join {{ ref("stg_schoolmint_grow__users") }} as uo on o.observer_id = uo.user_id
left join
    {{ ref("stg_schoolmint_grow__schools") }} as s
    on o.teaching_assignment_school = s.school_id
left join
    {{ ref("int_schoolmint_grow__observation_types") }} as ot
    on o.observation_type = ot.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt2
    on o.teaching_assignment_course = gt2.tag_id
left join
    {{ ref("stg_schoolmint_grow__generic_tags") }} as gt3
    on o.teaching_assignment_grade = gt3.tag_id
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on s.school_id = loc.grow_location_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
```

Notes on the diff:

- Replaced `gt` join (against `stg_schoolmint_grow__generic_tags`) with `ot`
  join against `int_schoolmint_grow__observation_types`. The implicit filter
  (`tag_type = 'observationtypes' AND archived_at IS NULL`) is now in the
  lookup.
- Added `ot.staff_observation_type_key` to the SELECT.
- Added `staff_observation_rubric_key` (pre-hashed; no `if()` wrapper because
  `rubric_id` is structurally non-null at this layer).
- Renamed source columns: `gt.name` → `ot.name`; `gt.abbreviation` →
  `ot.abbreviation`. Output names unchanged.

- [ ] **Step 4.2: Update the properties YAML.**

Replace the entire contents of
`src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml`
with:

```yaml
models:
  - name: int_schoolmint_grow__observations
    description: >-
      SchoolMint Grow observations enriched with school location, observer and
      teacher staff IDs, observation-type metadata, and pre-hashed foreign-key
      surrogates for staff_observation_type_key and
      staff_observation_rubric_key. One row per Grow observation_id.
    columns:
      - name: observation_id
        data_type: string
        description: SchoolMint Grow observation identifier.
        data_tests:
          - unique
          - not_null
      - name: rubric_id
        data_type: string
        description: >-
          SchoolMint Grow rubric identifier. Structurally non-null for all
          published, non-archived observations.
        data_tests:
          - not_null
      - name: staff_observation_rubric_key
        data_type: string
        description: >-
          Pre-hashed surrogate key derived from rubric_id. Generated with
          generate_surrogate_key(["rubric_id"]). Consumed by
          fct_staff_observations as its rubric FK.
        data_tests:
          - not_null
      - name: staff_observation_type_key
        data_type: string
        description: >-
          Pre-hashed surrogate key for the observation type. NULL when the
          observation's tag_id does not resolve to a non-archived
          observationtypes tag.
      - name: location_key
        data_type: string
        description: >-
          MD5 surrogate key for the canonical school location. Null when
          s.school_id does not match any grow_location_id in
          stg_google_sheets__people__locations.
        data_tests:
          - relationships:
              arguments:
                to: ref("dim_locations")
                field: location_key
      - name: rubric_name
        data_type: string
      - name: score
        data_type: float64
      - name: glows
        data_type: string
      - name: grows
        data_type: string
      - name: locked
        data_type: boolean
      - name: observed_at
        data_type: timestamp
      - name: observed_at_date_local
        data_type: date
      - name: academic_year
        data_type: int64
      - name: is_published
        data_type: boolean
      - name: magic_notes_text
        data_type: string
      - name: school_name
        data_type: string
      - name: observation_type_name
        data_type: string
      - name: observation_type_abbreviation
        data_type: string
      - name: observation_course
        data_type: string
      - name: observation_grade
        data_type: string
      - name: teacher_internal_id
        data_type: int64
      - name: observer_internal_id
        data_type: int64
```

- [ ] **Step 4.3: Build and test.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select int_schoolmint_grow__observations
```

Expected: model builds; `unique` on `observation_id` passes; `not_null` on
`rubric_id` and `staff_observation_rubric_key` pass; existing `relationships`
test on `location_key` still passes.

- [ ] **Step 4.4: Verify pre-hashed `staff_observation_type_key` matches
      existing fct values.**

```sql
with
    pr_branch as (
        select observation_id, staff_observation_type_key
        from `teamster-332318.{{ dev_schema }}.int_schoolmint_grow__observations`
    ),
    prod_fct as (
        select staff_observation_key, staff_observation_type_key
        from `teamster-332318.kipptaf.fct_staff_observations`
    )
select
    countif(p.staff_observation_type_key = pr.staff_observation_type_key
        or (p.staff_observation_type_key is null and pr.staff_observation_type_key is null))
        as matching,
    count(*) as total,
from prod_fct as p
inner join pr_branch as pr
    on p.staff_observation_key = to_hex(md5(pr.observation_id))
```

Expected: `matching = total`.

- [ ] **Step 4.5: Commit.**

```bash
git add src/dbt/kipptaf/models/schoolmint/grow/intermediate/int_schoolmint_grow__observations.sql \
        src/dbt/kipptaf/models/schoolmint/grow/intermediate/properties/int_schoolmint_grow__observations.yml
git commit -m "refactor(dbt): pre-hash observation FK keys in Grow intermediate (#3680)

Adds staff_observation_type_key (via int_schoolmint_grow__observation_types
left join) and staff_observation_rubric_key (pre-hashed from rubric_id)
to int_schoolmint_grow__observations. Adds unique test on observation_id
and not_null tests on rubric_id and staff_observation_rubric_key. Hash
compositions and values unchanged."
```

---

## Task 5 — Pre-hash `term_key` in `int_performance_management__observations`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__observations.sql`
- Modify:
  `src/dbt/kipptaf/models/performance_management/intermediate/properties/int_performance_management__observations.yml`

- [ ] **Step 5.1: Add `term_key` to both UNION branches.**

Replace the entire contents of
`src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__observations.sql`
with:

```sql
/* 2024+ All Observation Types */
select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.staff_observation_type_key,
    o.staff_observation_rubric_key,
    o.score as observation_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at as observed_at_timestamp,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    o.is_published,
    o.teacher_internal_id as employee_number,
    o.observer_internal_id as observer_employee_number,
    o.observation_type_name as observation_type,
    o.observation_type_abbreviation,
    o.observation_course,
    o.observation_grade,
    o.magic_notes_text as observation_notes,

    t.code as term_code,
    t.name as term_name,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "t.type",
                "t.code",
                "t.name",
                "t.start_date",
                "t.region",
                "t.school_id",
            ]
        )
    }} as term_key,

    case
        when o.score >= 3.495
        then 4
        when o.score >= 2.745
        then 3
        when o.score >= 1.745
        then 2
        when o.score < 1.75
        then 1
    end as overall_tier,

    case
        when t.code = 'PM1'
        then date(o.academic_year, 10, 1)
        when t.code = 'PM2'
        then date(o.academic_year + 1, 1, 1)
        when t.code = 'PM3'
        then date(o.academic_year + 1, 3, 1)
    end as eval_date,
from {{ ref("int_schoolmint_grow__observations") }} as o
inner join
    {{ ref("int_people__location_crosswalk") }} as lc
    on o.school_name = lc.location_name
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as t
    on o.observation_type_abbreviation = t.type
    and o.observed_at_date_local between t.start_date and t.end_date
    and lc.location_region = t.region
/* data prior to 2024 in snapshot */
where o.is_published and o.academic_year >= 2024

union all

/* 2023 Walkthroughs */
select
    o.observation_id,
    o.rubric_id,
    o.rubric_name,
    o.staff_observation_type_key,
    o.staff_observation_rubric_key,
    o.score as observation_score,
    o.glows,
    o.grows,
    o.locked,
    o.observed_at as observed_at_timestamp,
    o.observed_at_date_local as observed_at,
    o.academic_year,
    o.is_published,
    o.teacher_internal_id as employee_number,
    o.observer_internal_id as observer_employee_number,
    o.magic_notes_text as observation_notes,

    'Walkthrough' as observation_type,
    'WT' as observation_type_abbreviation,
    null as observation_course,
    null as observation_grade,

    t.code as term_code,
    t.name as term_name,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "t.type",
                "t.code",
                "t.name",
                "t.start_date",
                "t.region",
                "t.school_id",
            ]
        )
    }} as term_key,

    null as overall_tier,
    null as eval_date,
from {{ ref("int_schoolmint_grow__observations") }} as o
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as t
    on o.observed_at_date_local between t.start_date and t.end_date
    and t.type = 'WT'
where
    o.academic_year = 2023
    and o.is_published
    and (
        contains_substr(o.rubric_name, 'Walkthrough')
        or contains_substr(o.rubric_name, 'Strong Start')
    )
```

Notes on the diff:

- Added `o.staff_observation_type_key` and `o.staff_observation_rubric_key` to
  both branches (passthrough from upstream intermediate).
- Added `term_key` (6-column composition) to both branches.
- 2023 walkthrough branch's term LEFT JOIN doesn't carry `region` or `school_id`
  from `t` — those columns are NULL in unmatched rows, and the hash will be
  NULL-input-deterministic when the join misses, identical to today's
  `if(t_code is not null, ...)` outcome in the fact.

- [ ] **Step 5.2: Update properties — close the TODO and add `term_key`,
      `staff_observation_type_key`, `staff_observation_rubric_key` columns.**

Replace the entire contents of
`src/dbt/kipptaf/models/performance_management/intermediate/properties/int_performance_management__observations.yml`
with:

```yaml
models:
  - name: int_performance_management__observations
    config:
      materialized: table
    columns:
      - name: observation_id
        data_type: string
        data_tests:
          - unique
          - not_null
      - name: rubric_id
        data_type: string
      - name: rubric_name
        data_type: string
      - name: staff_observation_type_key
        data_type: string
        description: >-
          Pre-hashed FK to dim_staff_observation_types, passed through from
          int_schoolmint_grow__observations.
      - name: staff_observation_rubric_key
        data_type: string
        description: >-
          Pre-hashed FK to dim_staff_observation_rubrics, passed through from
          int_schoolmint_grow__observations.
      - name: term_key
        data_type: string
        description: >-
          Pre-hashed FK to dim_terms. Generated with generate_surrogate_key on
          (term type, code, name, start_date, region, school_id). NULL when the
          observation does not match a reporting term row.
      - name: observation_score
        data_type: float64
      - name: glows
        data_type: string
      - name: grows
        data_type: string
      - name: locked
        data_type: boolean
      - name: observed_at_timestamp
        data_type: timestamp
      - name: observed_at
        data_type: date
      - name: academic_year
        data_type: int64
      - name: is_published
        data_type: boolean
      - name: employee_number
        data_type: int64
      - name: observer_employee_number
        data_type: int64
      - name: observation_type
        data_type: string
      - name: observation_type_abbreviation
        data_type: string
      - name: observation_course
        data_type: string
      - name: observation_grade
        data_type: string
      - name: observation_notes
        data_type: string
      - name: term_code
        data_type: string
      - name: term_name
        data_type: string
      - name: overall_tier
        data_type: int64
      - name: eval_date
        data_type: date
```

- [ ] **Step 5.3: Build and test.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select int_performance_management__observations
```

Expected: model builds; `unique` and `not_null` on `observation_id` pass.

If the `unique` test fails, fan-out has appeared in production data since
BigQuery sampling on 2026-04-29. Investigate via:

```sql
select observation_id, count(*) as n
from `teamster-332318.{{ dev_schema }}.int_performance_management__observations`
group by observation_id
having n > 1
limit 20
```

Diagnose which join (terms or location_crosswalk) is fanning out and decide
whether to add a `qualify` clause or escalate to a separate issue. Do not
silently dedup.

- [ ] **Step 5.4: Verify `term_key` values match what fct_staff_observations
      currently produces.**

```sql
with
    pr_branch as (
        select observation_id, term_key
        from `teamster-332318.{{ dev_schema }}.int_performance_management__observations`
    ),
    prod_fct as (
        select staff_observation_key, term_key
        from `teamster-332318.kipptaf.fct_staff_observations`
    )
select
    countif(p.term_key = pr.term_key
        or (p.term_key is null and pr.term_key is null)) as matching,
    count(*) as total,
from prod_fct as p
inner join pr_branch as pr
    on p.staff_observation_key = to_hex(md5(pr.observation_id))
```

Expected: `matching = total`.

- [ ] **Step 5.5: Commit.**

```bash
git add src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__observations.sql \
        src/dbt/kipptaf/models/performance_management/intermediate/properties/int_performance_management__observations.yml
git commit -m "refactor(dbt): pre-hash term_key in perf_mgmt observations (#3680)

Pre-hashes term_key in both UNION branches of
int_performance_management__observations and passes through the
upstream staff_observation_type_key and staff_observation_rubric_key.
Closes the TODO with a real unique test on observation_id (verified
zero fan-out across 46,686 production rows). Hash composition and
values unchanged."
```

---

## Task 6 — Strip duplicated logic from `fct_staff_observations`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_observations.yml`

- [ ] **Step 6.1: Replace the SQL with the simplified version.**

Replace the entire contents of
`src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql` with:

```sql
select
    {{ dbt_utils.generate_surrogate_key(["o.observation_id"]) }} as staff_observation_key,

    if(
        o.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["o.employee_number"]) }},
        cast(null as string)
    ) as teacher_staff_key,

    if(
        o.observer_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["o.observer_employee_number"]) }},
        cast(null as string)
    ) as observer_staff_key,

    gro.location_key,

    o.term_key,

    o.staff_observation_type_key,

    o.staff_observation_rubric_key,

    o.academic_year,
    o.observation_score as score,
    o.overall_tier as overall_rating,
    o.observation_notes as notes,

    o.observed_at as observed_date_key,
    o.observed_at_timestamp as observed_timestamp,
    o.glows as positive_feedback,
    o.grows as growth_areas,
    o.locked as is_locked,
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("int_schoolmint_grow__observations") }} as gro
    on o.observation_id = gro.observation_id
```

Notes on the diff:

- Dropped the `observation_types` CTE entirely (lines 2-6 of the old file).
- Dropped the `observations_with_terms` CTE wrapper — no longer needed.
- Dropped the LEFT JOIN to `stg_google_sheets__reporting__terms` and the six
  `t.*` columns (now upstream).
- Dropped the LEFT JOIN to `int_people__location_crosswalk` (only used for
  region and term-join predicate; region was unused in the SELECT, term columns
  are now upstream).
- Dropped the `if()` wrapper on `staff_observation_type_key` — pre-hashed
  upstream, NULL flows naturally.
- Dropped the `if()` wrapper on `staff_observation_rubric_key` — pre-hashed
  upstream, never NULL.
- Dropped the `if()` wrapper on `term_key` — pre-hashed upstream, NULL flows
  naturally.
- Dropped the `row_number ... where rn = 1` dedup — verified no-op against
  current production; upstream `unique` test on `observation_id` guards against
  future fan-out.
- Kept the `gro` left-join for `location_key` only.

- [ ] **Step 6.2: Build and test.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select fct_staff_observations
```

Expected: model builds; all relationships tests pass with **zero orphans** on
`staff_observation_rubric_key` (was 23,372). Other relationship tests unchanged.

- [ ] **Step 6.3: Verify zero hash drift on `staff_observation_key`.**

```sql
with
    pr_branch as (
        select staff_observation_key
        from `teamster-332318.{{ dev_schema }}.fct_staff_observations`
    ),
    prod as (
        select staff_observation_key
        from `teamster-332318.kipptaf.fct_staff_observations`
    )
select
    (select count(*) from pr_branch) as pr_rows,
    (select count(*) from prod) as prod_rows,
    (select count(*) from pr_branch
        where staff_observation_key not in (select staff_observation_key from prod)) as in_pr_only,
    (select count(*) from prod
        where staff_observation_key not in (select staff_observation_key from pr_branch)) as in_prod_only
```

Expected: `pr_rows = prod_rows`; both `in_pr_only` and `in_prod_only` = 0.

- [ ] **Step 6.4: Verify zero hash drift on `staff_observation_rubric_key`,
      `term_key`, and `staff_observation_type_key`.**

```sql
with
    pr_branch as (
        select staff_observation_key, staff_observation_rubric_key, term_key, staff_observation_type_key
        from `teamster-332318.{{ dev_schema }}.fct_staff_observations`
    ),
    prod as (
        select staff_observation_key, staff_observation_rubric_key, term_key, staff_observation_type_key
        from `teamster-332318.kipptaf.fct_staff_observations`
    )
select
    countif(p.staff_observation_rubric_key is not distinct from pr.staff_observation_rubric_key) as rubric_match,
    countif(p.term_key is not distinct from pr.term_key) as term_match,
    countif(p.staff_observation_type_key is not distinct from pr.staff_observation_type_key) as type_match,
    count(*) as total,
from prod as p
inner join pr_branch as pr using (staff_observation_key)
```

Expected: `rubric_match = term_match = type_match = total`.

- [ ] **Step 6.5: Verify `fct_staff_observation_scores` rebuilds clean.**

`fct_staff_observation_scores` self-references `fct_staff_observations` (filter
`staff_observation_key in fct_staff_observations`). Rebuild it to confirm the
orphan FKs on `staff_observation_rubric_measurement_key` are gone:

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select fct_staff_observation_scores
```

Expected: model builds; relationships test on
`staff_observation_rubric_measurement_key` shows **zero orphans** (was 249,465).

- [ ] **Step 6.6: Promote the rubric_key relationships test to error severity
      and remove the stale TODO.**

Open `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_observations.yml`.
Locate the `staff_observation_rubric_key` column block (around line 59). Replace
the `data_tests:` block:

```yaml
data_tests:
  # TODO: #3712 — dim source is measurement-grain, excludes rubrics
  # without nested measurements. Promote to error once resolved.
  - relationships:
      arguments:
        to: ref('dim_staff_observation_rubrics')
        field: staff_observation_rubric_key
```

with:

```yaml
data_tests:
  - relationships:
      arguments:
        to: ref('dim_staff_observation_rubrics')
        field: staff_observation_rubric_key
      config:
        severity: error
```

The orphan rows are gone (Task 1 resolved them). Promoting to `error` locks the
invariant into CI.

- [ ] **Step 6.7: Re-run the rubric_key test to confirm error-level pass.**

```bash
uv run dbt test \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select fct_staff_observations
```

Expected: all relationships tests pass, including the now-`error`-severity one
on `staff_observation_rubric_key`.

- [ ] **Step 6.8: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql \
        src/dbt/kipptaf/models/marts/facts/properties/fct_staff_observations.yml
git commit -m "refactor(dbt): consume pre-hashed FK keys in fct_staff_observations (#3680, #3712)

Drops the inline observation_types CTE, the term LEFT JOIN, the
location_crosswalk join, the if() null-wrappers on three FK columns,
and the dead-code row_number dedup. Pulls staff_observation_type_key,
staff_observation_rubric_key, and term_key from upstream intermediates
where they're pre-hashed once. Promotes the
staff_observation_rubric_key relationships test to severity: error
now that orphans are resolved (closes #3712). Hash values unchanged
across all FKs."
```

---

## Task 7 — Add `staff_observation_type_key` FK to `dim_staff_observation_expectations`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_expectations.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_observation_expectations.yml`

- [ ] **Step 7.1: Add the join and the FK column to the SQL.**

Replace the entire contents of
`src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_expectations.sql`
with:

```sql
with
    scaffold as (
        select
            srh.employee_number,

            t.type,
            t.code,
            t.`name`,
            t.academic_year,
            t.start_date,
            t.end_date,
            t.region,
            t.school_id,
            t.is_current,

            srh.job_title,

            ot.staff_observation_type_key,

            row_number() over (
                partition by
                    srh.employee_number,
                    t.type,
                    t.code,
                    t.`name`,
                    t.start_date,
                    t.region,
                    t.school_id
                order by srh.effective_date_start desc
            ) as rn,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on srh.home_business_unit_name = t.region
            and (
                t.start_date
                between srh.work_assignment_actual_start_date and srh.effective_date_end
                or t.end_date
                between srh.work_assignment_actual_start_date and srh.effective_date_end
            )
            and t.type in ('PMS', 'PMC', 'TR', 'WT', 'O3')
        left join
            {{ ref("int_schoolmint_grow__observation_types") }} as ot
            on t.type = ot.abbreviation
        where
            srh.primary_indicator
            and srh.assignment_status = 'Active'
            and (srh.job_title like '%Teacher%' or srh.job_title like '%Learning%')
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "employee_number",
                "type",
                "code",
                "name",
                "start_date",
                "region",
                "school_id",
            ]
        )
    }} as staff_observation_expectation_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "type",
                "code",
                "name",
                "start_date",
                "region",
                "school_id",
            ]
        )
    }} as term_key,

    staff_observation_type_key,

    academic_year,
    is_current,

    job_title as position_title,
from scaffold
where rn = 1
```

Notes on the diff:

- Added
  `left join int_schoolmint_grow__observation_types as ot on t.type = ot.abbreviation`.
  Since the lookup's `abbreviation` column is unique-tested, the join cannot fan
  out the scaffold.
- Added `ot.staff_observation_type_key` to the scaffold CTE.
- Added `staff_observation_type_key` to the final SELECT.

- [ ] **Step 7.2: Update the properties YAML.**

Edit
`src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_observation_expectations.yml`.
Update the model description and add the new column. Replace the entire file
contents with:

```yaml
models:
  - name: dim_staff_observation_expectations
    description: >-
      Observation expectation scaffold. One row per staff member x observation
      type term. Built by crossing active teaching staff from roster history
      with PM/walkthrough/O3 term windows from the reporting terms sheet.
      Enables tracking whether each teacher received their expected observations
      in each period. Foreign keys to dim_staff, dim_terms, and
      dim_staff_observation_types.
    columns:
      - name: staff_observation_expectation_key
        data_type: string
        description: >-
          Surrogate primary key derived from employee_number and term composite
          fields. Generated with generate_surrogate_key(["srh.employee_number",
          "t.type", "t.code", "t.name", "t.start_date", "t.region",
          "t.school_id"]).
        constraints:
          - type: primary_key
            warn_unsupported: false
        data_tests:
          - unique
          - not_null

      - name: staff_key
        data_type: string
        description: >-
          Foreign key to dim_staff. Surrogate key derived from employee_number.
        constraints:
          - type: foreign_key
            to: ref('dim_staff')
            to_columns: [staff_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff')
                field: staff_key

      - name: term_key
        data_type: string
        description: >-
          Foreign key to dim_terms. Surrogate key derived from term type, code,
          name, start_date, region, and school_id.
        constraints:
          - type: foreign_key
            to: ref('dim_terms')
            to_columns: [term_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_terms')
                field: term_key

      - name: staff_observation_type_key
        data_type: string
        description: >-
          Foreign key to dim_staff_observation_types. Surrogate key resolved via
          int_schoolmint_grow__observation_types by joining the term type code
          (PMS, PMC, TR, WT, O3) to the SchoolMint Grow observation-type tag
          abbreviation. Non-nullable because the scaffold filters term types to
          the five observation types, all of which match a Grow tag 1:1.
        constraints:
          - type: foreign_key
            to: ref('dim_staff_observation_types')
            to_columns: [staff_observation_type_key]
            warn_unsupported: false
        data_tests:
          - not_null
          - relationships:
              arguments:
                to: ref('dim_staff_observation_types')
                field: staff_observation_type_key

      - name: academic_year
        data_type: int64
        description: >-
          Academic year of the observation expectation.

      - name: is_current
        data_type: boolean
        description: >-
          TRUE if the current date falls within this observation period.

      - name: position_title
        data_type: string
        description: >-
          Staff member's position title during the observation period.
```

- [ ] **Step 7.3: Build and test.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select dim_staff_observation_expectations
```

Expected: model builds; `not_null` and `relationships` on
`staff_observation_type_key` both pass.

- [ ] **Step 7.4: Commit.**

```bash
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_observation_expectations.sql \
        src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_observation_expectations.yml
git commit -m "fix(dbt): add staff_observation_type_key FK to expectations dim (#3641)

Joins int_schoolmint_grow__observation_types on term.type =
tag.abbreviation. All 5 staff-observation term types (PMS, PMC, TR,
WT, O3) match Grow generic_tags abbreviations 1:1, so the FK is
non-nullable. Closes the missing FK called out in the star-schema
spec audit."
```

---

## Task 8 — End-to-end verification and PR

**Files:** none modified — verification only.

- [ ] **Step 8.1: Build the full downstream graph from the touched staging
      models.**

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select \
        stg_schoolmint_grow__rubrics__measurement_groups__measurements+ \
        stg_schoolmint_grow__measurements+ \
        int_schoolmint_grow__observation_types+ \
        int_schoolmint_grow__observations+ \
        int_performance_management__observations+ \
        dim_staff_observation_expectations
```

Expected: every model and test passes. Pay attention to:

- `fct_staff_observations.staff_observation_rubric_key` relationships test → 0
  orphans (was 23,372)
- `fct_staff_observation_scores.staff_observation_rubric_measurement_key`
  relationships test → 0 orphans (was 249,465)
- `dim_staff_observation_expectations.staff_observation_type_key` relationships
  test → passes
- All other relationships and uniqueness tests unchanged.

- [ ] **Step 8.2: Spot-check downstream consumers of
      `int_performance_management__observations`.**

The dedup move is no-op today (verified zero fan-out at planning time), but
rebuild and sanity-check row counts on the consumers to confirm:

```bash
uv run dbt build \
    --project-dir=src/dbt/kipptaf/ \
    --target=dev \
    --select \
        int_performance_management__observation_details \
        int_performance_management__overall_scores \
        rpt_tableau__content_team \
        rpt_tableau__teacher_development \
        rpt_tableau__teacher_observations \
        rpt_tableau__pm_overall_scores \
        rpt_appsheet__seat_tracker_roster
```

Spot-check via BigQuery MCP that row counts match production within ~2% (no
observations lost, no fan-out introduced):

```sql
select
    (select count(*) from `teamster-332318.{{ dev_schema }}.rpt_tableau__teacher_development`) as pr_rows,
    (select count(*) from `teamster-332318.kipptaf.rpt_tableau__teacher_development`) as prod_rows
```

Repeat for each of the 7 consumers. Expected: counts match (or differ only by
current production vs. dev recency).

- [ ] **Step 8.3: Run `trunk check --ci` from the repo root.**

Trunk hooks aren't installed in worktrees, but the branch is checked out in the
main workspace — still good practice to validate before push:

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
```

Expected: no issues. If sqlfluff or yamllint flags anything, fix and amend the
relevant commit.

- [ ] **Step 8.4: Push the branch.**

```bash
git push -u origin cbini/fix/claude-batch-d-staff-observation-fks
```

- [ ] **Step 8.5: Open the PR.**

Use `mcp__github__create_pull_request` with title and body:

- **Title:**
  `fix(dbt): batch D — staff observation FK fixes & lookup centralization`
- **Body:** populate from `.github/pull_request_template.md`. Reference closes
  #3641, #3680, #3712, #3722; link the spec; summarize the orphan-FK fix metrics
  (273K → 0); note that the rubric-key relationships test is promoted to
  `severity: error`; note hash discipline (no values changed); flag the
  convention deviation on the two staging models.

- [ ] **Step 8.6: Verify dbt Cloud CI clean.**

Watch `gh pr checks` (no MCP equivalent for check status):

```bash
gh pr checks
```

Expected: dbt Cloud CI job passes. If it fails:

- Use `mcp__dbt__list_jobs_runs` and `mcp__dbt__get_job_run_error` (with
  `warning_only=true`) to inspect the failure.
- Use BigQuery MCP against the PR-branch CI schema
  (`dbt_cloud_pr_<ci_id>_<pr_num>_*`) to diagnose.

---

## Self-review checklist (run before pushing the branch)

- [ ] Every task ends with a commit. No staged-but-uncommitted state between
      tasks.
- [ ] No file touched by two consecutive tasks without an intervening commit.
- [ ] Every test mentioned in the spec is actually added in the plan (uniqueness
      on `int_schoolmint_grow__observation_types.tag_id`/`abbreviation`;
      uniqueness on `int_schoolmint_grow__observations.observation_id`;
      uniqueness on `int_performance_management__observations.observation_id`;
      not_null on `int_schoolmint_grow__observations.rubric_id` and
      `staff_observation_rubric_key`; relationships test on
      `dim_staff_observation_expectations.staff_observation_type_key`).
- [ ] Every hash claim ("values unchanged") has a verification query in the
      corresponding task.
- [ ] No `trunk fmt` invocations (PostToolUse hook handles it).
- [ ] No `git add -A`, `-u`, or `.` — every commit names files explicitly.
