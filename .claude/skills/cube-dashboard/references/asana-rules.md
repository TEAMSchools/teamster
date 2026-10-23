# Data Marts + Semantic Layer: Asana rules

The rules `scripts/asana_sync.py` applies to the "Data Marts + Semantic Layer"
project. Change a rule here and in the script together.

## Done and tags

- A measure row is **done** only if it is `cube-covered` AND `matched`: it ships
  in Cube today (every member its notes name is on a public view on `main`, and
  no stage blocker is open; a `Status:` line counts as naming a member only when
  it says `cube-covered`) and the latest validation found Cube equal to the
  dashboard. The sync ticks exactly those rows and unticks every other done row,
  saying why.
- Status tags: every measure row carries exactly one (plus `measure`), derived
  from evidence only, never from a tag already on the row. Nobody sets one by
  hand.
  - `cube-covered`: ships today (the row is done once it is also `matched`)
  - `cube-partial`: the latest validation found a Cube member missing (row stays
    open)
  - `mart-ready`: an open `cube:` or `view:` stage blocks it; needs Cube work
  - `mart-missing`: an open `mart:` stage or column addition blocks it; needs
    dbt work first
  - `untriaged`: no evidence either way; nobody has worked out what it needs yet
- Validation tags: every measure row carries exactly one, from the latest
  verdict in `~/asana-sync/validation/latest.json`. A blank never means
  anything.
  - `matched`: the latest run passed.
  - `mismatch`: the latest run found Cube's numbers differ (`fail`; `fix_cube`
    when Cube's own formula or fact differs; `fix_source` when the source data
    is wrong; `undecided` while the domain owner decides who fixes it; or
    `missing_member` when a member Cube lacks explains the gap). Only
    `missing_member` changes the status to `cube-partial`.
  - `unvalidated`: no run yet, or the latest run could not compare.
- Missing Cube member: when a member Cube lacks causes any part of a row's gap,
  the row is not shipped. `latest.json` lists those members as `reopen_for`; the
  sync unticks the row and tags it `cube-partial`. A member that only blocks
  some cuts (the dashboard slices by it, but no number moves) is linked as a
  blocker and does not reopen the row.
- Reused measures inherit: a measure row's verdict covers every tab that shows
  it, because the row is per measure, not per tab. A tab that computes it with a
  different calculation (a running or rolling variant, another code group) is
  not the same measure and needs its own run.

## When a cut needs its own Cube member

1. **A slice along a dimension needs no new member and counts as done.**
   Example: `count_students` grouped by school or `is_iep`.
2. **A definition with a rule, or a KPI people ask for by name, gets a named
   measure or segment, defined once.** Examples: thresholds, "missing", "on
   track", "chronic", `pct_proficient_crq`. Rows needing one stay open
   (`mart-ready`) until it exists.

Existing named measures are never removed just because they are slices; rule 1
only stops new pure-slice members.

## Structure

- One Asana task per table (named for the table), with stage subtasks `mart:`
  (only if the table is new), `cube:`, `view:` (facts only; dims join into the
  fact's view), then column additions.
- Dependencies: `mart` blocks `cube` blocks `view`; a measure row is blocked by
  the mart stage, addition or cube stage it needs.
- Each domain section has an `Open Issues — <Domain>` parent task (Assessments'
  is named `Open Issues`). Every follow-up a validation files sits under it.
- Shared section = conformed dims: calendar and org, the student spine, the
  staff spine.
