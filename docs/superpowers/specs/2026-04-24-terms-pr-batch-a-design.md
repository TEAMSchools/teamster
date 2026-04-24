# PR batch A (terms): fix 37M `term_key` orphans, close #3677

Closes #3677 and #3717.

## Context

`unique_dim_terms_term_key` warned on one duplicate row (#3677), and six
fact-side `term_key` `relationships` tests fail against `dim_terms` with a total
of ~37M orphan rows (#3717). BigQuery investigation showed:

- Every orphan `term_key` across all six consumers hashes to
  `eb66153e09d138b38fc979bff5b437d5` — the all-NULL output of
  `dbt_utils.generate_surrogate_key()`. All 37M orphans are rows where the
  fact-side LEFT JOIN to `stg_google_sheets__reporting__terms` failed to match
  and produced the null-composite hash rather than a real `term_key` or `NULL`.
- The current `stg_google_sheets__reporting__terms` has zero duplicates under
  the existing `term_key` composition
  `(type, code, name, start_date, region, school_id)`. #3677 appears already
  resolved in the sheet.

Grain analysis confirmed the current 6-tuple is the minimum key that the sheet's
data supports — smaller grains collapse legitimately distinct rows (e.g.,
SURVEY/SCD with multiple `name` values; WT/MG/O3 sharing codes like
`'1: Strong Start'`; SRE phases with the same code and different `end_date`).

## Root causes

### 1. Wrong filter literal in three grades facts

`fct_grades_assignments`, `fct_grades_category`, and `fct_grades_term` filter
their `reporting_terms` CTE by ``where `type` = 'quarter'``. No such code exists
in the sheet — actual codes are `RC`, `RT`, `SY`, `WT`, `SURVEY`, etc. The CTE
is empty, every LEFT JOIN returns null, and every row gets the null-composite
hash. Correct code is `'RT'`, matching the filter already used in
`dim_student_assessment_expectations`.

Impact: ~32.8M of the 37M orphans (24.6M `fct_grades_assignments`, 7.9M
`fct_grades_category`, 0.26M `fct_grades_term`).

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

`term_key` is unwrapped on all six consumer marts. Rows that don't match any RT
row get the null-composite hash, which fails `relationships` against any real
`dim_terms.term_key`. Wrapping makes unmatched rows honestly NULL; dbt's
`relationships` test ignores NULLs.

### 3. `dim_terms.region_key` is a diamond FK

`marts/CLAUDE.md` → "Strict-chain traversal": a dim must not carry an FK to a
deeper dim already reachable via its direct-parent chain. `dim_terms` has both
`location_key` (FK to `dim_locations`) and `region_key` (FK to `dim_regions`).
`dim_locations.region_key` already exists, so region is reachable via
`dim_terms → dim_locations → dim_regions`. The direct `dim_terms.region_key`
must be dropped. No mart `ref()`s `dim_terms` to read `region_key`, so blast
radius inside `marts/` is zero.

## Changes

### SQL

All six consumer marts adopt the nullable-FK shape on `term_key` (input list
unchanged — current 6-tuple):

```sql
if(
    rt.code is not null,
    {{ dbt_utils.generate_surrogate_key([
        "rt.type", "rt.code", "rt.name",
        "rt.start_date", "rt.region", "rt.school_id"
    ]) }},
    cast(null as string)
) as term_key,
```

`rt.code` is contract-enforced `not null` on the staging model, so it is the
cleanest match-guard.

Files:

- `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql` — change
  `'quarter'` → `'RT'` in the `reporting_terms` CTE; apply nullable wrap.
- `src/dbt/kipptaf/models/marts/facts/fct_grades_category.sql` — same.
- `src/dbt/kipptaf/models/marts/facts/fct_grades_term.sql` — same.
- `src/dbt/kipptaf/models/marts/facts/fct_staff_observations.sql` — apply
  nullable wrap (uses `t_*` alias variables; preserve them).
- `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`
  — apply nullable wrap.
- `src/dbt/kipptaf/models/marts/dimensions/dim_student_assessment_expectations.sql`
  — apply nullable wrap.

`dim_terms`:

- Drop the `region_key` SELECT block, its YAML column entry, and its
  `constraints:` FK to `dim_regions`.
- `term_key` composition and join logic unchanged.

### `dim_terms` FK surface

After the change, `dim_terms` carries `term_key` (PK) and `location_key` (FK to
`dim_locations`). Region attributes reach via
`dim_terms → dim_locations → dim_regions`.

### Column-naming audit spec

Append an entry to the "Enumerated surrogate-key changes" table in
`docs/superpowers/specs/2026-04-15-column-naming-audit.md` documenting the
nullable-wrap change on `term_key` across the six consumers. Rule 4 ("Null
handling changes") of the hash-change discipline applies: unmatched rows move
from the null-composite hash to `NULL`; matched rows' hash values are unchanged.

## Blast radius

- Matched rows in all six consumers: `term_key` values unchanged.
- Previously null-composite rows (~37M): become `NULL` (honest unmatched) or a
  real `term_key` (for the grades facts where `'quarter'` → `'RT'` now finds a
  match).
- `dim_terms.region_key` removal: no mart consumer reads it. Verify in PR that
  no `rpt_*`/extract/exposure reads it either.
- Cube semantic layer: if generated with a `region_key` FK declaration on
  `dim_terms`, that annotation must regenerate/update in the same PR.

## Residual out of scope

Some fact-side rows will remain unmatched (now `NULL` `term_key`) after the fix.
Causes, by consumer:

- `dim_student_assessment_expectations` — pre-AY24-25 Newark/Camden/Miami
  assessments have no matching per-region RT row in the sheet; 1.6M rows with
  `int_assessments__scaffold.region IS NULL` (upstream scaffold bug); small
  Paterson sheet coverage gap for 2026-02-02.
- Analogous pre-AY24 gaps expected in `dim_student_section_enrollments`,
  `fct_staff_observations`, and the three grades facts after the `'RT'` fix.

These are sheet-coverage and upstream-scaffold issues, not `term_key` logic
bugs. File follow-up issues:

1. Backfill pre-AY24 per-region RT rows in the reporting terms sheet (or
   document the historical `NULL` `term_key` as intentional).
2. Fix `int_assessments__scaffold.region IS NULL` population.

Neither blocks this PR.

## Issue #3677 disposition

Current `stg_google_sheets__reporting__terms` has 0 duplicate groups under the
6-tuple, and current `dim_terms` has 0 duplicate `term_key` values (verified via
BigQuery). The sheet owner appears to have cleaned the row between the issue
reopen and now. Close #3677 with a link to this PR and the BQ verification
query.

## Verification plan

1. Local staging build with `--full-refresh` of:
   `dim_terms+ fct_grades_assignments fct_grades_category fct_grades_term dim_student_section_enrollments dim_student_assessment_expectations fct_staff_observations`.
2. `dbt test --select dim_terms+` expects:
   - `unique_dim_terms_term_key` — pass.
   - Six `relationships` tests on fact-side `term_key` — pass (NULLs ignored by
     the test).
3. BigQuery spot check post-build, per consumer:
   ```sql
   select count(*) from <schema>.<model>
   where term_key is not null
     and term_key not in (select term_key from <schema>.dim_terms)
   ```
   Expect 0 on all six.
4. Confirm no `rpt_*`/extract/exposure references `dim_terms.region_key` before
   merge:
   ```bash
   grep -rn "dim_terms" src/dbt/kipptaf/models | grep region_key
   ```

## Acceptance

- [ ] `unique_dim_terms_term_key` clean.
- [ ] All six fact-side `term_key` `relationships` tests clean.
- [ ] `dim_terms.region_key` removed; no downstream reference remains.
- [ ] Hash-change entry added to column-naming audit spec.
- [ ] Follow-up issues filed: (a) sheet backfill of pre-AY24 per-region RT rows,
      (b) `int_assessments__scaffold.region` null population, (c) Paterson RT
      sheet coverage for early 2026.
- [ ] #3677 closed with link to BQ verification.
