# Batch D — staff observation FK fixes & lookup centralization

Closes [#3641](https://github.com/TEAMSchools/teamster/issues/3641),
[#3680](https://github.com/TEAMSchools/teamster/issues/3680),
[#3712](https://github.com/TEAMSchools/teamster/issues/3712),
[#3722](https://github.com/TEAMSchools/teamster/issues/3722).

#3712 is incidentally resolved: the staging filter removal in #3722 restores the
missing rubrics, and the relationships test on
`fct_staff_observations.staff_observation_rubric_key` is promoted to
`severity: error` once orphans clear.

## Problem

Three related defects in the staff-observation domain of the kipptaf dbt
project:

- **#3722** —
  `fct_staff_observation_scores.staff_observation_rubric_measurement_key` has
  249,465 orphan rows; `fct_staff_observations.staff_observation_rubric_key` has
  23,372 orphan rows. Both reference rubrics/measurements that don't appear in
  the corresponding dims.
- **#3641** — `dim_staff_observation_expectations` is missing the
  `staff_observation_type_key` FK required by the star-schema spec.
- **#3680** — `fct_staff_observations` resolves `staff_observation_type_key` by
  joining `stg_schoolmint_grow__generic_tags` inline, duplicating logic already
  present in `dim_staff_observation_types`.

## Root cause analysis

### #3722 — the orphans are entirely a staging-filter artifact

Two staging models filter to non-archived SchoolMint Grow rows only:

- `stg_schoolmint_grow__rubrics__measurement_groups__measurements`:
  `where r._dagster_partition_key = 'f'`
- `stg_schoolmint_grow__measurements`: `where _dagster_partition_key = 'f'`

`_dagster_partition_key` is the SchoolMint Grow `archived` flag (`f` = not
archived, `t` = archived). The `'t'` partitions hold 75 archived rubrics and 348
archived measurements that are still referenced by published, non-archived 2024+
observations.

BigQuery verification (run 2026-04-29 against production):

- All 92 distinct `rubric_id`s referenced by observation facts exist in
  `src_schoolmint_grow__rubrics` when both partitions are unioned (17 in `'f'`,
  75 in `'t'`).
- All 1,472 distinct `(rubric_id, measurement_id)` pairs from observation scores
  resolve when both partitions of `src_schoolmint_grow__rubrics` are read.
- All `measurement_id`s referenced exist in `src_schoolmint_grow__measurements`
  across both partitions.

Removing the `'f'` filters fully populates the dims; FK orphans go to zero. Fact
row counts do not change — only dim row counts grow.

The convention deviation (other Grow staging models keep the `'f'` filter) is
intentional for these two parents-of-orphan-FK-chains. Other Grow staging
filters are not transitively applied today: `stg_schoolmint_grow__observations`
keeps non-archived observations whose parent rubric/measurement happens to be
archived, so we lose only the metadata, not the fact rows. Consistent resolution
is to expose the parent metadata.

### #3641 — no crosswalk needed; abbreviations match Grow tags 1:1

`dim_staff_observation_expectations` scaffolds expectations from
`stg_google_sheets__people__reporting_terms.type` codes (`PMS`, `PMC`, `TR`,
`WT`, `O3`). `dim_staff_observation_types` is keyed on SchoolMint Grow `tag_id`.
BigQuery verification: all 5 staff-observation term-type codes match exactly one
non-archived Grow `generic_tags.abbreviation` row each, with no collisions. The
expectations dim can join Grow tags directly on `term.type = tag.abbreviation`
without an external crosswalk.

### #3680 — duplicated lookup logic

`fct_staff_observations` defines an inline `observation_types` CTE filtering
`tag_type = 'observationtypes' AND archived_at IS NULL` over
`stg_schoolmint_grow__generic_tags`. `dim_staff_observation_types` applies the
exact same filter. Same input rows, same hash composition (`["tag_id"]`), same
output values — logic duplicated across two models.

The same lookup is now needed by `dim_staff_observation_expectations` (#3641),
making centralization a hard requirement rather than a stylistic preference.

### Existing dead defensive code

`fct_staff_observations` includes
`row_number() over (partition by observation_id ...) as rn ... where rn = 1`,
defensively deduplicating in case the LEFT JOINs to
`stg_google_sheets__reporting__terms` and `int_people__location_crosswalk` in
`int_performance_management__observations` fan out. BigQuery verification:
46,686 rows in `int_performance_management__observations`, all distinct
`observation_id` — zero fan-out today. The defensive dedup is no-op and can be
removed; an upstream uniqueness test catches future fan-out at CI time.

## Scope

### What this builds

1. **Staging filter removal** — drop the archived-partition filter in
   `stg_schoolmint_grow__rubrics__measurement_groups__measurements` and
   `stg_schoolmint_grow__measurements`. Document the convention deviation in
   each model's `description:`.

2. **New intermediate model** — `int_schoolmint_grow__observation_types`
   centralizing the observation-type lookup with pre-hashed
   `staff_observation_type_key`:

   ```sql
   select
       {{ dbt_utils.generate_surrogate_key(["tag_id"]) }} as staff_observation_type_key,
       tag_id,
       abbreviation,
       `name`,
   from {{ ref("stg_schoolmint_grow__generic_tags") }}
   where tag_type = 'observationtypes' and archived_at is null
   ```

3. **Refactor `dim_staff_observation_types`** — `select` from the new
   intermediate; drop inline filter and inline hash. Hash values unchanged.

4. **Refactor `int_schoolmint_grow__observations`** — left-join the new
   intermediate on `o.observation_type = ot.tag_id`; expose
   `staff_observation_type_key` (drop `tag_id` from outputs — plumbing). Also
   pre-hash `staff_observation_rubric_key` from `o.rubric_id` (no `if()` wrapper
   — `rubric_id` is structurally non-null at this layer; verified across 121,771
   production rows).

5. **Refactor `int_performance_management__observations`** — pre-hash `term_key`
   in both UNION branches:

   ```sql
   {{ dbt_utils.generate_surrogate_key(
       ["t.type", "t.code", "t.name", "t.start_date", "t.region", "t.school_id"]
   ) }} as term_key,
   ```

   The 2023 walkthrough branch's term LEFT JOIN doesn't carry `region` or
   `school_id`, so its `term_key` is NULL when the join doesn't match —
   identical to today's `if(t_code is not null, ...)` outcome in the fact.

6. **Refactor `fct_staff_observations`** — substantial cleanup:
   - Drop the inline `observation_types` CTE and the `ot` LEFT JOIN.
   - Drop the LEFT JOIN to `stg_google_sheets__reporting__terms` and the six
     `t.*` pass-through columns.
   - Drop the `if()` wrappers for `staff_observation_type_key`,
     `staff_observation_rubric_key`, and `term_key`.
   - Drop the `row_number() ... where rn = 1` dedup (dead defensive code;
     replaced by upstream uniqueness test).
   - Pull pre-hashed `staff_observation_type_key`,
     `staff_observation_rubric_key` from `int_schoolmint_grow__observations`,
     and `term_key` from `int_performance_management__observations`.

7. **Add FK to `dim_staff_observation_expectations`** — left-join the new
   intermediate on `term.type = ot.abbreviation`, expose
   `ot.staff_observation_type_key`. NULLs propagate naturally for non-
   observation term types (ACT, AR, ATT, etc.).

### Tests added

- `int_schoolmint_grow__observation_types`: `unique` and `not_null` on both
  `tag_id` and `abbreviation`. The abbreviation uniqueness is load-bearing —
  `dim_staff_observation_expectations` joins on it.
- `int_schoolmint_grow__observations`: `unique` on `observation_id`; `not_null`
  on `rubric_id` and `staff_observation_rubric_key`.
- `int_performance_management__observations`: `unique` on `observation_id`,
  closing the existing `# TODO: add unique test` placeholder.
- `dim_staff_observation_expectations.staff_observation_type_key`:
  `relationships` to `dim_staff_observation_types.staff_observation_type_key`,
  `severity: error`, `config.where: "staff_observation_type_key is not null"`.

### Tests verified clean (post-PR)

- `fct_staff_observations.staff_observation_rubric_key` — currently 23,372
  orphans; expected zero after staging filter removal.
- `fct_staff_observation_scores.staff_observation_rubric_measurement_key` —
  currently 249,465 orphans; expected zero.
- `fct_staff_observations.staff_observation_type_key` — relationship test values
  unchanged; still passes.
- `fct_staff_observations.term_key` — relationship test values unchanged; still
  passes.

### Out of scope

- Filtering observations whose parent rubric/measurement is archived (the whole
  point of the #3722 fix is to keep these historical analytics).
- Other Grow staging models retaining the `_dagster_partition_key = 'f'` filter
  (intentional convention; only the two parents of orphan-FK chains change).
- Flattening `fct_staff_observation_scores`'s nested unnest into a new
  `int_schoolmint_grow__observation_scores` intermediate (YAGNI — no second
  consumer, no FK defensiveness gap; can be a separate issue if a use case
  emerges).
- Relocating `staff_observation_rubric_measurement_key` hashing upstream (would
  require the unnest-flattening intermediate; deferred with the above).
- Cube `accessPolicy` work (#3591) — separate workstream.

## Hash discipline

Per `src/dbt/kipptaf/models/marts/CLAUDE.md` "Hash-change discipline":

- `staff_observation_type_key` — same composition `["tag_id"]`, same source
  rows, identical values. No hash-changes table entry needed.
- `staff_observation_rubric_key` — same composition `["rubric_id"]`, same
  values. No entry.
- `term_key` — same 6-column composition, same join semantics, same resulting
  values. No entry.

## Star-schema diamond audit

Per the strict-chain rule in `marts/CLAUDE.md`, `fct_staff_observations`
post-refactor FKs:

- `teacher_staff_key` → `dim_staff`
- `observer_staff_key` → `dim_staff`
- `location_key` → `dim_locations`
- `term_key` → `dim_terms`
- `staff_observation_type_key` → `dim_staff_observation_types`
- `staff_observation_rubric_key` → `dim_staff_observation_rubrics`
- `observed_date_key` → `dim_dates`

No two FKs lead to the same ultimate dim. `region_key` reachable via
`dim_locations` chain (no direct FK on the fact). Diamond-free.

`dim_staff_observation_expectations` adds one FK (`staff_observation_type_key`)
— single-path, no diamond.

## Verification plan

After CI builds the PR-branch schema, query against
`dbt_cloud_pr_<ci_id>_<pr_num>_*` via BigQuery MCP:

1. Confirm orphan counts on
   `fct_staff_observations.staff_observation_rubric_key` and
   `fct_staff_observation_scores.staff_observation_rubric_measurement_key` = 0.
2. Confirm `fct_staff_observations` row count unchanged (no hash drift on
   `staff_observation_key`).
3. Confirm `dim_staff_observation_types` row count unchanged (filter and hash
   identical).
4. Confirm `dim_staff_observation_rubrics` and
   `dim_staff_observation_rubric_measurements` row counts increase by archived
   rubric/measurement counts (75 + 348 measurements).
5. Confirm `dim_staff_observation_expectations.staff_observation_type_key`
   relationships test passes.
6. Confirm zero hash deltas on `staff_observation_type_key`, `term_key`, and
   `staff_observation_rubric_key` between prod and PR-branch fact tables (a
   row-by-row hash comparison sanity check).

## File checklist

| File                                                                 | Change                                     |
| -------------------------------------------------------------------- | ------------------------------------------ |
| `stg_schoolmint_grow__rubrics__measurement_groups__measurements.sql` | drop partition filter                      |
| `stg_schoolmint_grow__measurements.sql`                              | drop partition filter                      |
| `int_schoolmint_grow__observation_types.sql`                         | new                                        |
| `int_schoolmint_grow__observation_types.yml` (properties)            | new                                        |
| `dim_staff_observation_types.sql`                                    | ref new intermediate                       |
| `int_schoolmint_grow__observations.sql`                              | join new intermediate; pre-hash rubric_key |
| `int_schoolmint_grow__observations.yml` (properties)                 | uniqueness, not_null tests                 |
| `int_performance_management__observations.sql`                       | pre-hash term_key                          |
| `int_performance_management__observations.yml` (properties)          | close TODO with unique test                |
| `fct_staff_observations.sql`                                         | drop inline CTE, joins, wrappers, dedup    |
| `fct_staff_observations.yml` (properties)                            | column updates                             |
| `dim_staff_observation_expectations.sql`                             | add FK column                              |
| `dim_staff_observation_expectations.yml` (properties)                | new column + relationships test            |
