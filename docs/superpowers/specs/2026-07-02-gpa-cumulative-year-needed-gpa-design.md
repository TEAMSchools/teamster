# Year-grain cumulative GPA and needed-GPA design

- **Date**: 2026-07-02
- **Issue**: [#4295](https://github.com/TEAMSchools/teamster/issues/4295)
- **Status**: Approved design, pending implementation plan

## Context

The GPA/gradebook dashboard rebuild needs two capabilities that the current
model layer cannot serve:

1. **Cumulative GPA by academic year** — what a student's cumulative Y1 GPA was
   as of the end of each academic year (freshman, sophomore, junior, ...), to
   show change over time.
2. **Needed weighted Y1 GPA** — the weighted Y1 GPA a student must earn in the
   current school year, given their currently enrolled credits, to finish with a
   projected cumulative Y1 GPA of 3.0 or higher.

Today the math lives in the `powerschool` source package
(`src/dbt/powerschool/models/sis/intermediate/int_powerschool__gpa_cumulative.sql`),
built per district, at grain `(studentid, schoolid)` — a single all-years rollup
"as of today" with `_projected` variants that blend stored Y1 grades and
in-progress final grades. The kipptaf model
(`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__gpa_cumulative.sql`)
is a thin `dbt_utils.union_relations` over Newark, Camden, and Miami plus GPA
bands. Nothing carries a year dimension; the existing dbt snapshot only covers
history from when snapshotting began, so it cannot backfill "end of freshman
year" for a current senior.

`stg_powerschool__storedgrades` retains every historical Y1 row by
`academic_year`, so year-end cumulative GPA is recomputable for all history.

## Goals

- Year-by-year cumulative GPA series per student, recomputed from stored Y1
  grades, with the in-progress current year as a projected data point.
- Needed-GPA-for-3.0 columns with a raw value plus an attainability flag.
- **Governance invariant**: any number that also exists on the original model
  must match it exactly — the current-year projected point is joined from the
  original model, never recomputed.

## Non-goals

- No `rpt_*`, mart, or extract surfacing — this effort ends at the INT layer
  (kipptaf unions included). A reporting view will sit between these models and
  any external consumer in a later effort, per repo convention.
- No unweighted needed-GPA twin (stakeholders asked for weighted only).
- No GPA bands or snapshot on the new year model.
- No Paterson rows (matches the existing kipptaf union).
- No historical needed-GPA ("what did they need entering 10th grade") — the
  metric exists for the current year only.

## Design

### Part 1 — needed-GPA columns on `int_powerschool__gpa_cumulative`

Four additive columns on the existing package model, derived inside the existing
`points_rollup` CTE from sums it already computes. Grain and existing columns
are untouched.

| Column                                | Definition                                                                                                                                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `potential_gpa_credits_current_year`  | Sum of `potentialcrhrs_projected` where `academic_year` = current — the currently enrolled GPA credit hours. Exposed so the needed number is auditable.                                                |
| `potential_gpa_credits_cum_projected` | Sum of `potentialcrhrs_projected` across all years — the denominator behind `cumulative_y1_gpa_projected`, exposed so the projected ratio is auditable and so the year model can join it (see Part 2). |
| `gpa_needed_for_cumulative_3_0`       | See formula below; rounded to 2 decimals like sibling columns. NULL (via `safe_divide`) when the student has no current-year GPA credits.                                                              |
| `is_cumulative_3_0_attainable`        | True when the needed value is less than or equal to the student's credit-weighted maximum achievable current-year weighted GPA. NULL when the needed value is NULL.                                    |

Formula, where `prior` = stored Y1 rows with `academic_year` before the current
year and `current` = current-year GPA credits:

```text
gpa_needed = (3.0 * (prior_credits + current_credits) - prior_weighted_points)
             / current_credits
```

Equivalent intuition form:
`3.0 + (3.0 - prior_gpa) * (prior_credits / current_credits)` — the deficit is
amplified by how much credit history the student carries.

**Governance property**: `prior_weighted_points` and `prior_credits` are the
same terms that produce `cumulative_y1_gpa`; `current_credits` is the same term
inside the denominator of `cumulative_y1_gpa_projected`. A student who earns
exactly the needed GPA lands at a projected cumulative of exactly 3.00 — one
code path, no reimplementation.

**Attainability max**: per student,
`sum(course potential credits * max grade_points of the course's weighted grade scale) / sum(course potential credits)`
over currently enrolled courses. Scale maxima come from
`int_powerschool__gradescaleitem_lookup` (max `grade_points` per
`gradescale_name`). Implementation note: verify `base_powerschool__final_grades`
exposes the weighted grade scale name for current-year courses; if not, resolve
it via the section/course grade scale.

**Edge behavior**:

- Freshman (no prior years): needed = 3.00 exactly (prior sums are zero).
- Already guaranteed: needed goes negative; flag stays true; BI renders as "on
  track regardless."
- Unreachable: raw value exposed (e.g., 4.8); flag false.
- Not enrolled / summer / graduated: needed and flag are NULL.
- Column description must note the fixed-denominator caveat: adds/drops change
  `potential_gpa_credits_current_year`, so the needed value is a live target
  that moves with schedule changes, not a promise.

### Part 2 — new model `int_powerschool__gpa_cumulative_year`

New model in the `powerschool` package (`models/sis/intermediate/`), grain
`(studentid, schoolid, academic_year)`. Accumulation is per student-school,
matching the existing model's convention — MS and HS series stay separate, and
school transfers split the series exactly as they do on today's tiles.

**Row source 1 — completed years (recomputed).** From
`stg_powerschool__storedgrades` Y1 rows using the same filters as the existing
stored branch (`storecode = 'Y1'`, `excludefromgpa = 0` for GPA terms,
`excludefromgraduation = 0` for earned credits, same
`int_powerschool__gradescaleitem_lookup` join for unweighted points). Aggregate
per `(studentid, schoolid, academic_year)`, then compute running sums over
`academic_year` within each student-school:

- `cumulative_y1_gpa` = running weighted points / running potential GPA credits,
  rounded to 2 decimals
- `cumulative_y1_gpa_unweighted` = running unweighted points / running potential
  GPA credits, rounded to 2 decimals
- `earned_credits_cum`, `potential_gpa_credits_cum` — running credit totals
  (audit trail for the ratios)
- `is_projected = false`

**Row source 2 — current year (joined, never recomputed).** For students with a
current-year enrollment (`base_powerschool__student_enrollments`, current
`yearid`, `rn_year = 1`), one row sourced from
`int_powerschool__gpa_cumulative`:

- `cumulative_y1_gpa` = the original model's `cumulative_y1_gpa_projected`
- `cumulative_y1_gpa_unweighted` = `cumulative_y1_gpa_projected_unweighted`
- `academic_year` = the `current_academic_year` var; `is_projected = true`
- `earned_credits_cum` = the original model's `earned_credits_cum_projected`
- `potential_gpa_credits_cum` = the original model's
  `potential_gpa_credits_cum_projected` (new column from Part 1)

The projected sums already include any stored current-year grades (the original
model's branches exclude already-stored courses from the in-progress branch), so
there is no double-count. Composite-key rule: rows for years before the current
year always come from the recompute; the current-year row always comes from the
join. The PK `(studentid, schoolid, academic_year)` holds.

**`grade_level`** per academic year is included (from
`base_powerschool__student_enrollments`, `rn_year = 1`) so consumers can label
freshman/sophomore/junior/senior without re-deriving. A retained student
legitimately shows the same grade level in two academic years; display handling
stays in BI.

### kipptaf layer

- New thin union model `int_powerschool__gpa_cumulative_year` over Newark,
  Camden, Miami (mirroring the existing union), adding `_dbt_source_project` via
  `extract_code_location`.
- New table entries in `sources-kippnewark.yml`, `sources-kippcamden.yml`,
  `sources-kippmiami.yml`.
- Properties YAML with descriptions and uniqueness test.
- The existing kipptaf union of `int_powerschool__gpa_cumulative` picks up the
  three new columns automatically via `select ur.*` once district prod tables
  rebuild; its properties YAML gains the new column entries.

## Deployment sequencing

`dbt_utils.union_relations` resolves columns at compile time from
`INFORMATION_SCHEMA`, so kipptaf cannot see new package columns until district
prod tables rebuild. Ship per the documented pattern in `src/dbt/CLAUDE.md`:

1. **PR 1 (package + districts)**: both `powerschool`-package model changes.
   District projects materialize on merge via Dagster.
2. **PR 2 (kipptaf)**: union model, sources entries, YAML updates — after
   district prod has rebuilt.

The single-PR cross-project workflow (`src/dbt/kipptaf/CLAUDE.md`) is the
fallback if a single PR is preferred; it requires seeding `zz_stg_*` schemas per
district.

## Testing

- **Uniqueness**: `dbt_utils.unique_combination_of_columns` on
  `(studentid, schoolid, academic_year)` for the package year model; plus
  `_dbt_source_relation` at the kipptaf layer.
- **dbt unit tests** (mocked inputs):
  - Running-sum accumulation across three mocked years produces the expected
    per-year cumulative values.
  - Needed-GPA algebra: freshman case returns exactly 3.0; negative-needed case;
    NULL when no current credits.
- **Reconciliation singular test** (permanent drift guard): for each
  student-school, the year model's latest stored (`is_projected = false`) row
  must equal the original model's stored-only `cumulative_y1_gpa` within 0.01
  (identical filters and rounding should make it exact; the tolerance absorbs
  float summation order at rounding boundaries).

## Validation (pre-merge / post-build)

- **Prod-data reconciliation of the current-year rows (required)**: after
  building with prod data, per district, join the year model's
  `is_projected = true` rows to `int_powerschool__gpa_cumulative` on
  `(studentid, schoolid)` and compare `cumulative_y1_gpa` against
  `cumulative_y1_gpa_projected` (and the unweighted pair). Expected result:
  exact match, zero exceptions — the value is joined, so any mismatch is a join
  bug (e.g., a student matched to the wrong school). Report as aggregates only
  (row counts, match rate, max absolute difference); no student-level values in
  any external write-up.
- Same aggregate comparison for latest stored-year rows vs `cumulative_y1_gpa`.
- Spot-check year-series row counts per district against distinct
  `(studentid, schoolid, academic_year)` in stored Y1 grades.
- Build path: package models build via a consuming district project dir with
  `--defer` to that district's prod manifest, per `src/dbt/CLAUDE.md`.

## Out of scope / follow-ups

- Reporting-layer surfacing (Tableau extract, marts/Cube, sheets) — separate
  effort once the INT layer lands.
- Any change to GPA-band logic or the existing snapshot definitions.
- Paterson inclusion — revisit only if the network turns on GPA reporting for
  Paterson.
