# PR batch A (terms): fix `dim_terms` duplicate and 37M `term_key` orphans

Closes #3677 and #3717.

## Context

`unique_dim_terms_term_key` warns on one duplicate row (#3677), and six
fact-side `term_key` `relationships` tests fail against `dim_terms` with a total
of ~37M orphan rows (#3717). Investigation via BigQuery MCP confirmed every
orphan hashes to the same value: `eb66153e09d138b38fc979bff5b437d5` — the
all-NULL `dbt_utils.generate_surrogate_key()` output. All 37M orphans are rows
where the fact-side LEFT JOIN to `stg_google_sheets__reporting__terms` failed to
match and produced a null-composite hash rather than a real `term_key`.

## Root causes

### 1. Wrong filter literal in three grades facts

`fct_grades_assignments`, `fct_grades_category`, and `fct_grades_term` filter
their `reporting_terms` CTE by ``where `type` = 'quarter'``. The sheet has no
`type='quarter'` — actual codes are `RC`, `RT`, `SY`, `WT`, `SURVEY`, etc. The
CTE is empty, every LEFT JOIN returns null, and every row gets the
null-composite hash. Correct code is `'RT'` (reporting term), matching the
filter already used in `dim_student_assessment_expectations`.

Impact: ~32.8M of the 37M orphans.

### 2. Missing nullable-FK wrapper on `term_key`

Per `src/dbt/CLAUDE.md` → "Nullable surrogate keys", `generate_surrogate_key()`
hashes NULL inputs into a deterministic placeholder — it never returns NULL.
Columns derived via LEFT JOIN must wrap the call:

```sql
if(
    source_col is not null,
    {{ dbt_utils.generate_surrogate_key(["source_col"]) }},
    cast(null as string)
) as fk_col,
```

`term_key` is unwrapped on all six marts. Rows that don't match any RT row get
the null-composite hash, which fails `relationships` against any real
`dim_terms.term_key`. Wrapping it makes unmatched rows honestly NULL; dbt's
`relationships` test ignores NULLs.

### 3. `region` is a redundant join column and hash input

`school_id` is network-unique in PowerSchool (and in `stg_people__locations`'s
`powerschool_school_id`). Including `region` in the join and in the `term_key`
hash composition adds no identity signal and blocks the pre-AY24 legacy RT rows
from matching post-refactor facts: the sheet has 760 legacy RT rows with
`region IS NULL` spanning 2002–2026, and per-region rows only start 2024-07-01
(2025-07-01 for Paterson). With `region` in the join, a fact row dated 2020 with
`region='Newark'` can't match the legacy row for its school_id because
`'Newark' = NULL` is false.

Pre-merge BigQuery checks confirmed it is safe to drop `region` from the join
and hash:

- No `(school_id, start_date, end_date)` duplicates in RT rows.
- No overlapping RT date ranges for any `school_id`.
- Legacy rows end 2024-06-30 per school; per-region rows start 2024-07-01 —
  clean AY24 handoff, no double-match.

### 4. `dim_terms.region_key` is a diamond FK

`marts/CLAUDE.md` → "Strict-chain traversal": a dim must not carry an FK to a
deeper dim already reachable via its direct-parent chain. `dim_terms` has both
`location_key` (FK to `dim_locations`) and `region_key` (FK to `dim_regions`).
`dim_locations.region_key` already exists, so region is reachable via
`dim_terms → dim_locations → dim_regions`. The direct `dim_terms.region_key` is
a diamond and must be dropped.

No mart references `dim_terms` directly via `ref()` — consumption is via
`term_key` FK only — so removing the column has no downstream blast radius
inside `marts/`.

### 5. Source sheet duplicate (#3677)

One `(type, code, name, start_date, region, school_id)` row is duplicated in
`src_google_sheets__reporting__terms`. Once `region` drops out of the `term_key`
composition (change 3), re-verify whether the duplicate still produces a
duplicate hash under the reduced key — it probably does, since the duplicate
rows share `school_id`. Clean the source sheet per issue #3677's recommended
option 1.

## Changes

### SQL

All six marts adopt the same `term_key` shape:

```sql
if(
    rt.code is not null,
    {{ dbt_utils.generate_surrogate_key(
        ["rt.type", "rt.code", "rt.name", "rt.start_date", "rt.school_id"]
    ) }},
    cast(null as string)
) as term_key,
```

Join conditions become `(school_id, date-range)` + `type = 'RT'`. Files:

- `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql` — `'quarter'`
  → `'RT'`; drop `rt.region` from hash + join; nullable wrap.
- `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql` — same.
- `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql` — same.
- `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql` — drop region
  from hash + join; nullable wrap. (Uses `t_*` alias variables; adapt.)
- `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
  — drop region from hash + join; nullable wrap.
- `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql`
  — drop region from hash + join; nullable wrap.

`dim_terms`:

- Drop `region` from the `term_key` hash composition (new input list:
  `[type, code, name, start_date, school_id]`).
- Drop the `region_key` column, its YAML entry, and any `constraints:` FK to
  `dim_regions`.

### Source sheet

Edit `src_google_sheets__reporting__terms` in Google Sheets to remove the one
duplicate row identified in #3677. Verify uniqueness under the reduced
`(type, code, name, start_date, school_id)` key before saving. Coordinate with
the sheet owner.

### Column-naming audit spec

Append an entry to the "Enumerated surrogate-key changes" table in
`docs/superpowers/specs/2026-04-15-column-naming-audit.md` documenting the
`term_key` composition change (`region` dropped) on `dim_terms` and all six
consumers.

## Blast radius

- `term_key` hash values change for every matched row in `dim_terms` and all six
  consumers (composition change). This is a full-refresh required change; no
  external consumers read `term_key` as a natural value, so the hash turnover is
  invisible downstream.
- 37M null-composite rows become `NULL` `term_key` (honest unmatched) or a real
  `term_key` (newly matched against legacy RT rows, post-AY24 boundary fix).
- `dim_terms.region_key` removal — no consumer inside `marts/` reads this
  column. Verify no rpt/extract/exposure reads it before merge.
- Cube semantic layer: `region_key` will need to be removed from any Cube
  definition that declares the FK. Check `cube.yml` / Cube-generated semantic
  layer artifacts in the PR.

## Residual out of scope

The `int_assessments__scaffold.region IS NULL` residual (~1.6M rows, of which
273K also have `administered_at IS NULL`) is an upstream data-quality issue in
the assessment scaffold, not a terms issue. Open a follow-up to fix scaffold
region population. Does not block this PR.

The ~105 Paterson 2026-02-02 residual is small and likely a `school_id` mismatch
in Paterson RT sheet coverage. Bundle into the same follow-up.

## Verification plan

1. Pre-merge: confirm no new `(school_id, date-range)` fan-out by re-running the
   overlap check against whatever sheet state exists at merge time.
2. Local staging build with `--full-refresh` of:
   `dim_terms+ fct_grades_assignments fct_grades_category fct_grades_term dim_student_section_enrollments dim_student_assessment_expectations fct_staff_observations`.
3. `dbt test --select dim_terms+` expects:
   - `unique_dim_terms_term_key` — pass (after sheet dedup).
   - Six `relationships` tests on `term_key` — pass.
4. BigQuery MCP spot check post-build:
   ```sql
   select count(*) from <schema>.fct_grades_assignments
   where term_key is not null
     and term_key not in (select term_key from <schema>.dim_terms)
   ```
   Expect 0 on all six consumers.

## Acceptance

- [ ] `unique_dim_terms_term_key` clean.
- [ ] All six fact-side `term_key` `relationships` tests clean.
- [ ] `dim_terms.region_key` removed; no downstream breakage.
- [ ] Hash-change entry added to column-naming audit spec.
- [ ] Follow-up issue filed for `int_assessments__scaffold.region` nulls and
      Paterson RT sheet coverage gap.
