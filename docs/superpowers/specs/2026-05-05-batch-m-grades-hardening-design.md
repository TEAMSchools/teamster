# Batch M — grades hardening design

Closes [#3677](https://github.com/TEAMSchools/teamster/issues/3677),
[#3688](https://github.com/TEAMSchools/teamster/issues/3688),
[#3691](https://github.com/TEAMSchools/teamster/issues/3691),
[#3738](https://github.com/TEAMSchools/teamster/issues/3738),
[#3739](https://github.com/TEAMSchools/teamster/issues/3739).

## Problem

Five open issues in [PR batch M](https://github.com/orgs/TEAMSchools/projects/4)
target the grades-mart join chain and its term-staging dependency. The fixes are
independent at the file level but share a thematic surface
(`stg_google_sheets__reporting__terms`, `dim_terms`, `fct_grades_*`,
`bridge_course_section_terms`, `int_powerschool__gradebook_assignments_scores`).

Each issue's claims were verified against current code and live data. Several
required reframing — captured per-section below.

## Goals

- Resolve the grades-mart hardening backlog atomically as one PR.
- Keep all changes outside `marts/` strictly **additive**: no rename, drop, or
  semantic shift of any column consumed by a non-mart model. Mart-internal
  changes are unconstrained.
- Fix the Paterson CASE bug in `stg_google_sheets__reporting__terms` (data
  correctness).
- Resolve `dim_terms`'s internal inconsistency (hash on raw region, join on
  canonical city).
- Replace brittle `regexp_extract(_dbt_source_relation, 'kipp(\w+)_')` region
  derivation in three mart models with a join to canonical staging locations.
- Defend the term-staging RT grain against future drift via a uniqueness test.
- Expose Ed-Fi-aligned `points_earned` / `numeric_grade_earned` on
  `fct_grades_assignments` while preserving the legacy `score_entered` /
  `scoretype` outputs in the upstream intermediate model for tableau-extract
  consumers.

## Non-goals

- Renaming `stg_google_sheets__reporting__terms.city` to `region`. After
  scrutiny, `city` is not a misnomer — Newark / Camden / Miami / Paterson are
  city names that double as region identifiers in this org. The original framing
  of #3691 as a "naming bug" does not hold.
- Migrating the 13 non-mart consumers of `rt.city` / `rt.region` to canonical
  values. The raw-region staging contract carries inconsistent long/short values
  that are real data debt, but resolving it requires upstream cleanup
  coordinated with consumers — out of scope for this batch.
- Cube semantic-layer updates for the dropped `score` / `score_type` mart
  columns. Cube is outside the dbt project; consumer-side update happens
  separately.
- A defensive `qualify` tiebreaker in `fct_grades_category` (originally proposed
  by #3738). The project's no-manual-deduplication convention
  (`src/dbt/CLAUDE.md`) prohibits it, and the issue itself notes no current
  fan-out. A staging-layer uniqueness test catches future drift more cleanly.

## Verification of issue claims

Five issues, audited against production data:

### #3677 — source duplicate in `stg_google_sheets__reporting__terms`

**Claim**: `unique_dim_terms_term_key` warns on 1 duplicate row.

**Reality**: Production staging has zero duplicates today. The duplicate may
have already been resolved at source, or only manifested during a specific
historical full-refresh. The raw external sheet cannot be queried via BigQuery
MCP (Drive credentials denied), so post-merge confirmation requires a CI
rebuild.

**Implication**: Treat as a test-severity follow-up — promote
`unique_dim_terms_term_key` from `warn` to `error` once a clean rebuild confirms
no duplicates. If a fresh rebuild surfaces duplicates, fix at the sheet first.

### #3688 — split polymorphic `fct_grades_assignments.score`

**Claim**: `score` carries POINTS / PERCENT / GRADESCALE / COLLECTED values
disambiguated by sibling `score_type`. Row counts: 20M / 4.4M / 197K / 9.7K.

**Reality**: Counts confirmed (20.3M / 4.4M / 197K / 9.7K). The
`points_possible → max_points` rename mentioned in the issue body shipped
already in PR #3676.

**Reframe**: Issue says the work is in "the staging models that drive
`fct_grades_assignments`." Actually the polymorphic branching already lives in
the **intermediate** model `int_powerschool__gradebook_assignments_scores`
(lines 47-51 today branch a single `score_entered` value off `scoretype`). The
fix splits at the intermediate layer, not staging.

The intermediate model also exposes `score_entered` and `scoretype` directly to
downstream tableau extracts:
`int_tableau__gradebook_audit_assignments_student.sql`,
`int_tableau__gradebook_audit_assignments_teacher.sql`,
`int_tableau__gradebook_audit_categories_teacher.sql`,
`int_tableau__gradebook_audit_flags.sql`, plus `rpt_tableau__gradebook_audit` (5
sites), `rpt_tableau__gradebook_es_comments`,
`rpt_tableau__gradebook_ms_hs_comments`. Removing those columns from the
intermediate model would break all of them.

### #3691 — `city` vs `region` in `stg_google_sheets__reporting__terms`

**Claim**: The `city` column holds canonical region values and should be renamed
to `region`. `dim_terms.region_key` derives from `t.city`.

**Reality, three findings**:

1. There is no `region_key` column in `dim_terms`. The model exposes `term_key`,
   `location_key`, `type`, `term_code`, `term_name`, dates, `academic_year`,
   `fiscal_year`, `grade_band`, `data_freeze_date`, `is_current` — region is
   **not** a column on the dim. `t.region` (raw) feeds the `term_key` hash;
   `t.city` (canonical) feeds the `sch.location_key` join. That's an internal
   inconsistency: hash inputs and join keys disagree about which form of region
   to use.

2. The CASE expression at lines 4-13 has a bug: it matches `'KIPP Paterson'` but
   not bare `'Paterson'`. 30 rows have raw `region = 'Paterson'` and canonical
   `city = NULL`.

3. The "rename" framing doesn't hold up. Newark / Camden / Miami / Paterson are
   city names; calling a column of city values `city` is correct. The confusion
   is conceptual, not a column-naming bug. Renaming would also break 5 non-mart
   consumers (`int_topline__state_assessments_weekly.sql:18`,
   `int_topline__star_assessment_weekly.sql:13`,
   `int_topline__dibels_benchmark_weekly.sql:17`,
   `int_topline__iready_diagnostic_weekly.sql:48`,
   `rpt_tableau__iready_apm.sql:92`) and silently change values for 8 more that
   read `rt.region` (raw).

**Reframe**: Drop the rename. Fix the Paterson CASE bug. Resolve the `dim_terms`
hash-vs-join inconsistency by switching the hash input to `t.city`. Both are
pure-additive outside marts (the value Paterson rows now carry on `city` was
previously NULL; nothing currently reads it as non-NULL).

### #3738 — defensive `QUALIFY` in `fct_grades_category`

**Claim**: Add a `qualify row_number() = 1` tiebreaker to the `reporting_terms`
join, mirroring `fct_grades_assignments.sql:124-129`. Verified no fan-out today.

**Reality**: The qualify at `fct_grades_assignments.sql:128-133` is the
**enrollment-date fan-out tiebreaker** (TODO #3633), not an RT-term defense.
There is no existing RT-term qualify pattern in the codebase to copy.

**Reframe**: `src/dbt/CLAUDE.md` prohibits manual `qualify`-based deduplication.
With no current fan-out, the operationally correct response is a uniqueness test
on the term-staging RT grain — duplicates would fail at build time before
reaching any mart. No mart-level `qualify`.

### #3739 — regex region extraction in mart models

**Claim**: `fct_grades_term.sql:101` and `bridge_course_section_terms.sql:30`
derive region via `initcap(regexp_extract(_dbt_source_relation, 'kipp(\w+)_'))`.
Replace with `extract_code_location()` macro or
`int_people__location_crosswalk`.

**Reality**:

- Line numbers off — actual locations are `fct_grades_term.sql:117` and
  `bridge_course_section_terms.sql:30`.
- `extract_code_location()` returns the full code-location (`kippcamden`,
  `kippnewark`, etc.), not the short capitalized region name (`Camden`,
  `Newark`). The current regex captures the suffix and `initcap()`s it, which
  produces the short form. Direct macro substitution does not work.
- The same anti-pattern lives in `dim_terms.sql:34-35` —
  `lower(concat('kipp', t.city)) = regexp_extract(sch._dbt_source_relation, r'(kipp\w+)_')`.
  Issue body doesn't mention it but it should be fixed in this batch.

**Reframe**: Use `stg_google_sheets__people__locations` (canonical-grain, one
row per logical school) rather than `int_people__location_crosswalk`
(alias-grain). The canonical staging model exposes both `dagster_code_location`
and `location_region` and is already the source for `dim_locations`. Three sites
in scope: `fct_grades_term`, `bridge_course_section_terms`, `dim_terms`.

## Design

### Section 1 — Paterson CASE fix (#3691, #3677 enabler)

Edit the CASE expression in `stg_google_sheets__reporting__terms.sql`:

```sql
case
    when region in ('Newark', 'TEAM Academy Charter School') then 'Newark'
    when region in ('Camden', 'KIPP Cooper Norcross Academy') then 'Camden'
    when region in ('KIPP Miami', 'Miami') then 'Miami'
    when region in ('KIPP Paterson', 'Paterson') then 'Paterson'
end as city,
```

Only change: `('KIPP Paterson')` → `('KIPP Paterson', 'Paterson')`. Effect: 30
rows that today have `city = NULL` will gain `city = 'Paterson'`. No existing
consumer reads those NULL values as non-NULL, so the change is purely additive
to the `city` column's value distribution.

### Section 2 — `dim_terms` internal consistency fix (#3691)

In `dim_terms.sql`:

- Line 11 (`term_key` hash inputs): `"t.region",` → `"t.city",`
- Lines 30-35 (join clause to `stg_powerschool__schools`): rewritten by
  Section 4.

The hash-input switch produces hash churn for ~720 `term_key` values where raw
`t.region` differs from canonical `t.city` (e.g.,
`'TEAM Academy Charter School'` rows previously hashed with that long string;
they will re-hash with `'Newark'`). Plus an additional ~30 rows that gain a
non-null hash component due to the Paterson fix.

Hash churn is acceptable: `term_key` is a `dim_terms` PK, no facts have
materialized FK history to it. Downstream relationship tests will rebuild
through Dagster's auto-materialization.

### Section 3 — Test coverage for term staging (#3677, #3738)

Two changes in
`src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__reporting__terms.yml`:

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

This catches future RT-grain drift at staging build time, before mart fan-out.
Replaces the proposed mart-level `qualify` (#3738).

In `src/dbt/kipptaf/models/marts/dimensions/properties/dim_terms.yml`, promote
`unique_dim_terms_term_key` severity from `warn` to `error`. Verify during
PR-branch CI that no duplicates surface; if any do, fix at the sheet before
merge.

### Section 4 — Replace regex region extraction (#3739)

Three mart files: `fct_grades_term.sql`, `bridge_course_section_terms.sql`,
`dim_terms.sql`. Each adds a CTE pulling the canonical mapping from the
locations sheet, then joins on `dagster_code_location` to retrieve
`location_region`.

Pattern (illustrative, applied per file with site-specific aliases):

```sql
with
    -- ... existing CTEs ...
    location_regions as (
        select dagster_code_location, location_region,
        from {{ ref("stg_google_sheets__people__locations") }}
    )
-- ...
left join
    location_regions as lr
    on lr.dagster_code_location
       = {{ extract_code_location(<source_alias>) }}
-- then: rt.region = lr.location_region
```

Replaces:

- `fct_grades_term.sql:117`:
  `initcap(regexp_extract(fg._dbt_source_relation, r'kipp(\w+)_')) = rt.region`
- `bridge_course_section_terms.sql:30`:
  `initcap(regexp_extract(sec._dbt_source_relation, r'kipp(\w+)_')) = rt.region`
- `dim_terms.sql:34-35`:
  `lower(concat('kipp', t.city)) = regexp_extract(sch._dbt_source_relation, r'(kipp\w+)_')`

**Verification before commit**: confirm
`(dagster_code_location → location_region)` is functionally unique in
`stg_google_sheets__people__locations`. The canonical model has one row per
logical school, so multiple schools may share a code-location, but they should
all share a region. A `select distinct dagster_code_location, location_region`
should produce one row per code-location.

`kipptaf` itself never appears in `_dbt_source_relation` for these models — they
source from per-region district packages (`kippnewark`, `kippcamden`,
`kippmiami`, `kipppaterson`). No fallback needed.

### Section 5 — Split polymorphic score (#3688)

#### Section 5.1 — Intermediate model (additive)

In
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gradebook_assignments_scores.sql`,
add two new columns alongside the existing `score_entered`:

```sql
if(a.scoretype = 'POINTS', s.scorepoints, null) as points_earned,
if(
    a.scoretype in ('PERCENT', 'GRADESCALE', 'COLLECTED'),
    safe_cast(s.actualscoreentered as numeric),
    null
) as numeric_grade_earned,
```

`scoretype` and `score_entered` remain unchanged for the
`int_tableau__gradebook_audit_*` and `rpt_tableau__gradebook_*` consumers.

#### Section 5.2 — Mart fact

In `src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`, replace the
`asg.score_entered as score` and `asg.scoretype as score_type` lines with the
typed columns:

```sql
asg.points_earned,
asg.numeric_grade_earned,
asg.totalpointvalue as max_points,
asg.assign_final_score_percent as score_percent,
```

`fct_grades_assignments.yml` updated: drop `score` and `score_type` column
entries; add `points_earned` and `numeric_grade_earned` with
`data_type: float64`, descriptions, and the standard column metadata.

Cube is the only known consumer of the dropped mart columns; consumer-side
update happens in the Cube repo, separately.

## Risk and rollout

| Risk                                                                                                    | Source      | Mitigation                                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Hash churn on `dim_terms.term_key`                                                                      | Section 2   | Acceptable; `term_key` is a PK with no historical FK chain. Auto-materialization rebuilds downstream.                                                                                          |
| Stale view definitions for downstream consumers of `dim_terms` after column-derivation change           | Section 4   | Per `src/dbt/CLAUDE.md` "Column-rename refactors strand dependent prod views," check `INFORMATION_SCHEMA.VIEWS.view_definition` post-merge; rematerialize stragglers via Dagster `launch_run`. |
| Crosswalk join produces fan-out if `dagster_code_location → location_region` is not functionally unique | Section 4   | Verify in CI before merge; if fanout, switch to `select distinct` CTE form.                                                                                                                    |
| Cube break on dropped `score` / `score_type`                                                            | Section 5.2 | Cube update tracked separately. PR body lists affected mart columns.                                                                                                                           |
| `unique_dim_terms_term_key` fires post-severity-bump if a sheet duplicate exists                        | Section 3   | Verify via PR-branch CI rebuild before flipping severity; if dup found, fix at sheet.                                                                                                          |

## Validation

Before merge, run on PR branch:

- `dbt build --select stg_google_sheets__reporting__terms+ --exclude resource_type:test`
  to rebuild affected staging.
- `dbt test --select stg_google_sheets__reporting__terms` to confirm new
  uniqueness test passes.
- `dbt build --select dim_terms fct_grades_term fct_grades_category fct_grades_assignments bridge_course_section_terms int_powerschool__gradebook_assignments_scores`
  to rebuild affected marts and the intermediate.
- `dbt test --select dim_terms+1` to verify `unique_dim_terms_term_key` passes
  at error severity.
- BigQuery MCP query against PR-branch schema: confirm
  `(dagster_code_location → location_region)` unique in
  `stg_google_sheets__people__locations`.
- BigQuery MCP query: confirm row counts on `fct_grades_assignments` unchanged
  vs. main, and `points_earned + numeric_grade_earned` non-null counts match the
  prior `score`-non-null count by `scoretype`.

## Out-of-scope follow-ups captured

- Upstream cleanup of the raw `region` column in
  `stg_google_sheets__reporting__terms` (consistent canonical values across the
  8 non-mart consumers that read it).
- Migrating the 5 non-mart consumers of `rt.city` to a future canonical column
  if/when the rename happens.
- Cube schema update for `fct_grades_assignments` column changes.
