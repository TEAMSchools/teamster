# Pension plan join fix — design

Refs #6325 (Zendesk ticket 487626).

## Intent

The Pension Checker tab of the NJ Certification Dashboard shows a pension plan
for 114 of the 1,244 staff with an active NJ pension in ADP. HR Operations uses
the tab to find certified staff still enrolled in PERS so they can move them to
TPAF, and cannot do that while most plans are missing.

## Cause

The pension join in `int_people__staff_roster_history.sql` filters on
`pbe.rn_enrollment_recent = 1`. The staging model ranks that column across all
of a person's benefits (`partition by employee_number, enrollment_status`), so
for most staff the rank-1 row is a non-pension benefit and the `plan_name`
filter in the same `on` clause rejects it.

## Approaches

### Fixing the join

- **A. Delete the `rn_enrollment_recent = 1` predicate from the join.** Chosen.
  Active NJ pension rows are unique per `position_id` (1,300 rows on 1,300
  positions), so the rank adds nothing to the join.
- **B. Re-partition `rn_enrollment_recent` by plan in the staging model.**
  Rejected: changes a shared staging column's meaning to guard against
  duplicates that do not occur, and widens the CI rebuild.
- **C. Add a current-pension-per-position model.** Rejected: a new model, tests,
  and docs for a one-line bug.

### Which history rows get the plan

The ADP file is a current-state snapshot, overwritten on every load, so it holds
only each position's current enrollment. Joined on `position_id` alone, that
plan lands on every history row for the position, including rows dated before
the enrollment started (6,711 rows on 1,146 positions in prod).

- **Current row only.** Chosen by the user: the plan is ADP's current
  enrollment, so it appears only where `is_current_record` is true and no past
  row implies a plan the data cannot vouch for.
- **Rows inside the enrollment window.** Rejected: correct where filled, but a
  blank before the start date reads as either "not enrolled" or "in a plan ADP
  no longer reports".
- **Snapshot ADP going forward.** Rejected for now: records only future switches
  and adds a model.

## Goals

- `nj_pension_plan_name` is populated on the current record of every position
  with an active NJ pension (1,244 staff in prod on 2026-11-09).
- `nj_pension_plan_name` is null on every non-current history row.
- The roster row count does not change, and no current-row non-null
  `nj_pension_plan_name` value changes.

## Design

In `int_people__staff_roster_history.sql`, delete
`and pbe.rn_enrollment_recent = 1` from the pension join and select
`if(w.is_current_record, pbe.plan_name, null) as nj_pension_plan_name`. The
condition sits in the `select`, not the join's `on`, because a from-table
predicate in a `left join` `on` is the pattern S11 flags. Update the column's
`description` in the properties YAML to say it holds the current enrollment on
the current record only.

## Non-goals

- Ingesting the `Cert_export_to_tableau` Google Sheet through Dagster and dbt.
- The workbook's reference to a missing `nj_cert_export` tab.
- Snapshotting pension enrollment history.
- Removing the now-unused `rn_enrollment_recent` column.

## Guard

The existing uniqueness test on `int_people__staff_roster_history` catches a
fan-out if ADP ever sends 2 active NJ pensions for one position.

## Verification

`uv run dbt build --select int_people__staff_roster_history+` in the worktree,
then compare the dev build to prod: staff with a pension plan on the current
record rises from 114 to 1,244, non-current rows carry no plan, and row counts
and existing current-row values hold.
