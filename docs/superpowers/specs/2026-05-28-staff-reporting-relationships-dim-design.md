# Staff Reporting-Relationships Dim Design

**Date:** 2026-05-28 **Status:** Active **Issue:**
[#3838](https://github.com/TEAMSchools/teamster/issues/3838)

## Overview

Add a person-grained, point-in-time dimension —
`dim_staff_reporting_relationships` — that exposes "who was this staff member's
manager on date D." It lets the gradebook, observations, and surveys Cube cubes
surface a teacher's / observed staff's / survey subject's manager via a single
date-range join plus a role-playing `staff_manager` cube (`extends: staff`),
without denormalizing manager attributes onto `dim_staff` and without each
consuming cube re-deriving a fragile multi-table period intersection.

This supersedes the original #3838 plan (denormalize `manager_name` /
`manager_staff_key` onto `dim_staff`), which violated the marts strict-chain
rule and was current-only.

## Goals

- A reusable dbt mart dim, keyed by the subordinate's `staff_key`, that answers
  "manager at a point in time" with one date-range join.
- Strict-chain compliant: `dim_staff` is untouched; manager identity is a role
  FK (`manager_staff_key`) reachable by traversal, not a denormalized name.
- Resolve the primary-assignment + reporting-relationship period intersection
  **once, upstream**, so gradebook / observations / surveys cubes each do a
  single clean join.

## Non-goals

- **Cube YAML implementation** (the `staff_reporting_relationships` cube, the
  `staff_manager extends staff` alias, the per-fact joins) — that lands in the
  Cube model work on `cristinabaldor/feat/claude-cube-model-yaml-design`. This
  spec covers the dbt dim only, and documents the intended Cube consumption for
  context.
- **The "who can see their data today" access chain** — the `queryRewrite`
  `dim_staff.reporting_chain` segment is a separate current-transitive-closure
  security mechanism, already scoped to the cube-infra follow-up. Out of scope.
- **Widening manager history** — pre-2021 NJ (Dayforce-era) manager coverage is
  owned by [#3869](https://github.com/TEAMSchools/teamster/issues/3869). This
  dim reads downstream of that and will gain coverage when #3869 ships.

## Background: why this isn't reachable today

`dim_work_assignment_reporting_relationships` already carries
`manager_staff_key` (role FK → `dim_staff`, SCD2 by effective period), but it
can't serve the consumer question as-is:

1. **Key mismatch.** It's keyed by `work_assignment_key`. The facts carry a
   _person_ FK (`teacher_staff_key`, `observer_staff_key`, `subject_staff_key` —
   i.e. `staff_key`). There is no shared join key; reaching it requires hopping
   through `dim_staff_work_assignments`.
2. **Grain mismatch / fan-out.** `staff_key` is **not unique** in
   `dim_staff_work_assignments` — a person can hold multiple assignments (e.g.
   teacher + coach). So `staff_key → work_assignment_key` is one-to-many, and
   there is no single "this person's manager at date D" row addressable by
   `staff_key` without first picking the **primary** assignment at that date.

So "manager at date D" is a three-table, point-in-time intersection:

```text
primary assignment @ D        (dim_work_assignment_primary,                SCD2)
  → reporting-relationship @ D (dim_work_assignment_reporting_relationships, SCD2)
    → manager_staff_key        (role FK → dim_staff)
```

Pushing that 3-table date overlap into every consuming cube would repeat fragile
period-intersection SQL and invite grain blow-ups. This dim computes it once.

## Source models (all marts; intra-mart refs)

| Model                                         | Grain                                   | Columns used                                                                               |
| --------------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------ |
| `dim_staff_work_assignments`                  | 1 / `work_assignment_key` (Type 1)      | `work_assignment_key`, `staff_key`                                                         |
| `dim_work_assignment_primary`                 | 1 / `(work_assignment_key, eff. start)` | `work_assignment_key`, `is_primary_position`, `effective_start_date`, `effective_end_date` |
| `dim_work_assignment_reporting_relationships` | 1 / `(work_assignment_key, eff. start)` | `work_assignment_key`, `manager_staff_key`, `effective_start_date`, `effective_end_date`   |

All three are mart dims; `dim_staff_reporting_relationships` references them as
intra-mart refs (permitted per `marts/CLAUDE.md`). No new intermediate model is
required — the inputs are already SCD2-shaped.

## Design: `dim_staff_reporting_relationships`

**Location:** `src/dbt/kipptaf/models/marts/dimensions/` (+ `properties/`).

**Grain:** one row per `(staff_key, effective_start_date)` — the subordinate's
manager over a contiguous effective period.

**Columns:**

| Column                             | Type    | Notes                                                                      |
| ---------------------------------- | ------- | -------------------------------------------------------------------------- |
| `staff_reporting_relationship_key` | string  | PK = `generate_surrogate_key(["staff_key", "effective_start_date"])`       |
| `staff_key`                        | string  | Subordinate. FK → `dim_staff`.                                             |
| `manager_staff_key`                | string  | Role FK → `dim_staff`. Nullable (no number mapping, or pre-#3869 history). |
| `effective_start_date`             | date    | `GREATEST` of the two source spans' starts.                                |
| `effective_end_date`               | date    | `LEAST` of the two source spans' ends. `9999-12-31` sentinel for open.     |
| `is_current`                       | boolean | `effective_end_date = '9999-12-31'`.                                       |

**Build logic:**

1. **Primary spans per staff.** From `dim_work_assignment_primary` filtered to
   `is_primary_position = true`, joined to `dim_staff_work_assignments` on
   `work_assignment_key` to attach `staff_key`. Yields, per staff, the periods
   during which a given assignment was their primary assignment.
2. **Manager spans.** From `dim_work_assignment_reporting_relationships` —
   `work_assignment_key`, `manager_staff_key`, effective span.
3. **Intersect** (1) and (2) on `work_assignment_key` where the periods overlap:
   - `effective_start_date = GREATEST(primary.start, reporting.start)`
   - `effective_end_date   = LEAST(primary.end,   reporting.end)`
   - keep rows where `effective_start_date <= effective_end_date`
4. Project to `staff_key` grain (the primary filter guarantees ≤1 primary
   assignment per staff at any instant — see "Uniqueness" below).

Both sources use the `9999-12-31` open-ended sentinel (no NULL), so `GREATEST` /
`LEAST` are NULL-safe without `COALESCE`.

**Materialization:** `table` (override in `properties/...yml` per
`src/dbt/CLAUDE.md`). The model sits atop three view-materialized dims; a table
avoids deep view nesting and keeps the Cube-side date-range join from
compounding toward BigQuery's 16-view limit at query time.

**Nullable FK handling:** `manager_staff_key` is already null-wrapped at source
(`if(... is not null, surrogate, null)`); carry it through unchanged. No
`not_null` test on it. `staff_key` is the PK input and must be non-null, but
`dim_staff_work_assignments.staff_key` is itself nullable (assignments whose
`associate_oid` has no active number mapping). Filter `staff_key is not null` in
step 1 — a work assignment not attributable to a person cannot anchor a
person-grained row.

## Tests

- `unique` + `not_null` on `staff_reporting_relationship_key`.
- `relationships` on `staff_key` → `dim_staff.staff_key`.
- `relationships` on `manager_staff_key` → `dim_staff.staff_key` (nullable FK;
  passes on NULLs).
- `dbt_utils.expression_is_true: effective_start_date <= effective_end_date`
  (mirrors the guard on `dim_work_assignment_primary`).
- Contract enforced + `materialized: table` via `properties` yml.

## Intended Cube consumption (separate work — documented for context)

In the Cube model project:

- A standalone cube `staff_reporting_relationships` (`public: false`,
  `sql_table: kipptaf_marts.dim_staff_reporting_relationships`). The `staff_`
  prefix keeps it under `queryRewrite`'s `startsWith("staff")` gate.
- A role alias `staff_manager` (`extends: staff`, `public: false`) joined from
  `staff_reporting_relationships` on `manager_staff_key`.
- Each staff-keyed fact date-range-joins it, `many_to_one` (same shape as the
  student ELL/IEP/meal status dims):

  ```text
  {staff_reporting_relationships.staff_key} = {CUBE}.<role>_staff_key
  AND CAST({CUBE}.<record_date_key> AS TIMESTAMP)
      BETWEEN CAST({staff_reporting_relationships.effective_start_date} AS TIMESTAMP)
      AND     CAST({staff_reporting_relationships.effective_end_date}   AS TIMESTAMP)
  ```

- Manager name = `staff_manager.full_name`, reached purely by traversal. Detail
  views add `staff_manager_*` PII fields to the relevant `excludes:` list.

## Open questions / verify at implementation

1. **Primary exclusivity.** The `(staff_key, effective_start_date)` PK assumes
   at most one assignment is `is_primary_position = true` per staff at any
   instant. Verify in prod before trusting the surrogate; if two assignments are
   ever concurrently primary, the intersection fans out and the grain needs a
   tiebreaker (or the PK must include `work_assignment_key`, changing the
   grain).
2. **Coverage.** Confirm populated `manager_staff_key` rates per region/era
   (expect NULLs pre-#3869 for NJ). Treat high-NULL as a coverage gap, not a
   broken join.
3. **Staff with no primary assignment** (e.g. pending hires, gaps) simply have
   no row for that period; consumers `LEFT JOIN` and see a NULL manager. Confirm
   that's the desired behavior for gradebook/observations denominators.

## Validation plan

- `uv run dbt build --select dim_staff_reporting_relationships+` against
  `kipptaf` (worktree project dir).
- Spot-check a known staff member with a manager change and/or multiple
  assignments: confirm one row per contiguous manager period, correct
  `manager_staff_key` per `effective_*` window, `is_current` on the open period.
- Confirm PK uniqueness holds in prod-shaped data (open question 1).
