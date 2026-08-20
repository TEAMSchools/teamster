# PowerSchool dlt intraday cursor: `whenmodified` to `transaction_date`

Date: 2026-08-06 Issue:
[#4754](https://github.com/TEAMSchools/teamster/issues/4754)

## Problem

The PowerSchool dlt intraday sensor detects change with a signature of
`COUNT(*)` plus `MAX(cursor_column)`. An in-place UPDATE that changes row
content without advancing the cursor produces an identical signature, so the
sensor skips and the warehouse copy stays stale. Tables configured
`intraday: true` with `nightly: false` have no full-refresh backstop, so the
staleness persists indefinitely.

This is not a defect in the sensor. `probe_signature` and `_compute_changed`
behave exactly as written. The cursor is the wrong signal for the tables in
scope.

## Evidence

Ops corrected `homeschoolid` for 10 Paterson staff. A live read-only probe over
the SSH tunnel compared all 219 rows of PowerSchool `users` against the
warehouse copy:

```text
rows live / warehouse    : 219 / 219   (no inserts, no deletes)
homeschoolid changed     : 10 rows
whenmodified changed     : 0 rows
transaction_date changed : 105 rows

live   COUNT(*)          : 219                   stored baseline: 219
live   MAX(whenmodified) : 2026-08-05T00:01:03   stored baseline: 2026-08-05T00:01:03
live   MAX(transaction_date): 2026-08-06T07:17:33  stored baseline: 2026-08-05T00:01:04
```

The probe signature was byte-identical to the stored baseline, so the sensor
correctly reported no change. `transaction_date` moved on all 10 drifted rows
and its max advanced past the baseline, so the sensor would have fired on that
cursor.

`transaction_date` tracks updates reliably in every district. Of the rows
modified in 2026 across all three districts, every one carries a
`transaction_date` at or after its `whenmodified`:

| district     | rows modified in 2026 | transaction_date null | stale | tracks |
| ------------ | --------------------- | --------------------- | ----- | ------ |
| kipppaterson | 55                    | 0                     | 0     | 55     |
| kippnewark   | 179                   | 0                     | 0     | 179    |
| kippcamden   | 50                    | 0                     | 0     | 50     |

`transaction_date` is 26 to 45 percent NULL overall in Newark and Camden, but
those are rows untouched since the column was introduced. `MAX()` ignores NULLs,
so the signature is unaffected.

## Scope

Three tables have both `whenmodified` and `transaction_date` and currently use
`whenmodified` as their cursor. The set is identical in all three districts:

- `users`
- `schoolstaff`
- `sectionteacher`

Every other exposed table has only `whenmodified` and no better cursor
available. Those are excluded: there is no evidence their updates fail to bump
the cursor, and a fix without a demonstrated defect is speculative.

Ten sibling tables in the same config already use `transaction_date`, including
the four largest (`attendance`, `pgfinalgrades`, `storedgrades`, `cc`). The
three tables in scope are the outliers, not the precedent.

## Decision

Change `cursor_column` from `whenmodified` to `transaction_date` for the three
tables, in each of the three district configs. Nine lines across three files. No
Python changes.

Files:

- `src/teamster/code_locations/kipppaterson/powerschool/sis/dlt/config/assets.yaml`
- `src/teamster/code_locations/kippnewark/powerschool/sis/dlt/config/assets.yaml`
- `src/teamster/code_locations/kippcamden/powerschool/sis/dlt/config/assets.yaml`

## Behavior on deploy

The change remediates the existing drift without a manual run:

1. Merge triggers the code location redeploy; the sensor rebuilds its
   `PowerSchoolTable` list with the new cursors.
2. The next 15-minute tick probes `MAX(transaction_date)` rather than
   `MAX(whenmodified)`.
3. The stored dlt baseline still holds the old `whenmodified` value, so the
   signatures differ and `_compute_changed` selects all three tables.
4. Each table full-replaces, and the new baseline persists carrying the
   `transaction_date` signature.
5. dbt automation rebuilds `stg_powerschool__users`; the
   `rpt_powerschool__autocomm_teachers` join matches on the corrected
   `homeschoolid`, and affected staff return to the nightly 3am extract.

The three tables total 219 to 52k rows per district. The one-time reload is well
inside the `dlt_powerschool_*` pool limit of 1.

## Verification

After the deploy lands:

1. Confirm the sensor tick selected the three tables rather than skipping.
2. Re-run the live drift comparison for Paterson `users`. Expect `homeschoolid`
   drift of 0 rows.
3. Confirm the affected staff appear in `rpt_powerschool__autocomm_teachers`.

Existing sensor unit tests are unaffected because no Python changes.

## Rollback

Revert the nine lines. The next tick observes a signature differing from the
stored `transaction_date` baseline, reloads once, and re-baselines on
`whenmodified`. One extra reload in either direction, on small tables, with no
destructive step.

## Alternatives considered

**Probe both columns and take the max of the two.** Strictly cannot regress,
being a superset of both signals. Rejected: it requires changing `cursor_column`
to a list and reshaping the signature, which invalidates the stored baseline for
every table in every district config, not just the three in scope. Given that
`transaction_date` tracked every 2026 modification in all three districts, the
additional surface area buys almost nothing.

**Set `nightly: true` on the three tables.** Simple and a guaranteed backstop.
Rejected: it leaves the intraday tick blind and corrects once a night, accepting
up to 24 hours of staleness while a working intraday signal goes unused. It
treats the symptom rather than the wrong cursor.

**A config parity test across the three district files.** The three configs are
copies of one PowerSchool schema and drifted into disagreement, which is how
this defect arose. Considered and deliberately excluded from this change to keep
it minimal; it remains available as separate work.

## Out of scope

- The 10 exposed tables with only `whenmodified`. No demonstrated defect.
- Nightly backstop policy for the large `transaction_date` tables.
- The circular join in `rpt_powerschool__autocomm_teachers`, which requires a
  staff member's `homeschoolid` to already be correct in order to include them
  in the extract that sets it. Recorded in
  [#4754](https://github.com/TEAMSchools/teamster/issues/4754); it needs its own
  design.
