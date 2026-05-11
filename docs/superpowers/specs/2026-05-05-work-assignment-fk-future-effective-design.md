# Design: `dim_staff_work_assignments` represents latest-known state per item_id

Issue: [#3822](https://github.com/TEAMSchools/teamster/issues/3822)

## Problem

Two `relationships` tests warn against `dim_staff_work_assignments`:

| Child model                                | Column                | Orphan rows |
| ------------------------------------------ | --------------------- | ----------: |
| `dim_work_assignment_organizational_units` | `work_assignment_key` |           4 |
| `dim_work_assignment_locations`            | `work_assignment_key` |           2 |

Both warn on the same two `work_assignment_key`s (4 + 2 rows = SCD2 history per
key). Same counts in production.

## Root cause

`dim_staff_work_assignments` (Type 1) reads
`int_adp_workforce_now__workers__work_assignments` and filters
`where is_current_record`. `is_current_record` is defined upstream as
`current_date BETWEEN effective_date_start AND effective_date_end` — true only
when today falls in the worker-version's effective range.

Both orphan item_ids (`9204842524489_2`, `9205031688430_2`) have
`actual_start_date` in the future (2026-05-11, 2026-05-18). They live in
worker-versions whose `effective_date_start` is in the future, so
`is_current_record = false`. The parent dim drops them; the children
(`dim_work_assignment_organizational_units`, `dim_work_assignment_locations`)
build SCD2 across all worker-versions and include them → orphans.

## Decision

Reframe the parent's grain. `dim_staff_work_assignments` should represent
**every work assignment ADP has shown us, with the latest-known attributes per
`item_id`** — not "what's active today." The narrow FK fix is a symptom of the
parent being too restrictive.

This serves reporting use cases that need pending future hires, currently active
assignments, and historical/withdrawn assignments side-by-side. Consumers that
want the active-today set filter on a new `is_current` column.

## Changes

### 1. `dim_staff_work_assignments` (parent)

Replace the `where is_current_record` filter with `dbt_utils.deduplicate`, keyed
on `item_id` and ordering by `effective_date_start desc` so each row carries the
latest worker-version that contained the assignment:

```sql
work_assignments as (
    {{
        dbt_utils.deduplicate(
            relation=ref("int_adp_workforce_now__workers__work_assignments"),
            partition_by="item_id",
            order_by="effective_date_start desc",
        )
    }}
),
```

Add a new `is_current` BOOLEAN column on the SELECT:

```sql
if(
    wa.actual_start_date <= current_date('{{ var("local_timezone") }}')
    and (
        wa.termination_date is null
        or wa.termination_date >= current_date('{{ var("local_timezone") }}')
    ),
    true,
    false
) as is_current,
```

Properties yml updates:

- Add `is_current` column entry with description ("True when today falls within
  this work assignment's `actual_start_date` … `termination_date` range. False
  for pending future assignments and ended assignments.").
- Update model description to note the dim now represents every assignment ADP
  has shown us with latest-known attributes per `item_id`.
- No change to `work_assignment_key` `unique` test — `dbt_utils.deduplicate`
  preserves uniqueness on the partition column.

### 2. Children — no SQL changes

`dim_work_assignment_organizational_units` and `dim_work_assignment_locations`
already build SCD2 across all worker-versions. Both `relationships` warnings
clear because the parent now contains every `item_id` ever seen.

### 3. Downstream consumer audit

Read each direct/role-played consumer of `dim_staff_work_assignments` and look
for "every dim row is active today" assumptions. Where a consumer filters out
non-current rows in a way that loses reporting value, remove the filter. Where
it (correctly) joins via date or termination semantics, no change.

Consumers to audit:

- `fct_staff_attrition`
- `bridge_survey_expectations`
- `fct_work_assignment_compensation` (role-played FK)
- `fct_work_assignment_additional_earnings` (role-played FK)
- `dim_staff` (role-played FK)
- `cube.yml` exposure — surface `is_current` so BI consumers can recreate the
  active-today view in the semantic layer.

## Pre-merge checklist

- [ ] `uv run dbt build --select dim_staff_work_assignments+ --project-dir src/dbt/kipptaf`
      — both `relationships` warnings resolved.
- [ ] Spot-check: `9204842524489_2` and `9205031688430_2` appear in
      `dim_staff_work_assignments` with `is_current = false`.
- [ ] Each downstream consumer audited; any filter removals or `is_current`
      additions documented in the PR.
- [ ] Diamond-path scan on touched mart models (no new FK chains introduced).
- [ ] Column-naming rubric (R1–R10) check on `is_current` — passes (R3 `is_`
      prefix, source-agnostic, ubiquitous).
- [ ] Project board scanned for incidentally-resolved bonus issues.

## Out of scope

- Promoting `dim_staff_work_assignments` to SCD Type 2. Latest-known-per-
  item_id covers the reporting need without the additional grain.
- Restructuring `int_adp_workforce_now__workers__work_assignments`. The
  intermediate's "one row per (worker-version × item_id)" grain is correct for
  the children's SCD2 builds.
- Withdrawn-assignment data-quality monitoring. Not currently observed; can be
  added later if it materializes.
