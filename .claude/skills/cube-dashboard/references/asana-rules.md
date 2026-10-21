# Data Marts + Semantic Layer: Asana rules

The rules `scripts/asana_sync.py` applies to the "Data Marts + Semantic Layer"
project. Change a rule here and in the script together.

## Done and tags

- Rows are a dashboard's measure subtasks and its dimension rows (see
  _Structure_). The sync tags each `measure` or `dimension`, and the rules below
  apply to both.
- A row is **done** when it is live in Cube: every member its notes name is on a
  public view on `main`, and no blocker on the row is open. Done is what the
  semantic layer status page counts as ready, so it means people can query the
  metric today, not that it matches the dashboard. Validation never holds a row
  open. The sync ticks exactly those rows and unticks every other done row,
  saying why.
- A row whose notes name a member on `main` but which still needs Cube work (a
  threshold measure, a grain, a band) is held by a blocker: a
  `cube: <member> on <cube>` subtask of the table task. The preview lists rows
  whose members are on `main` but a blocker is open: move a cut's blocker to its
  dimension row, and close a stage that has shipped.
- Status tags: an open row carries at most one, from its open blockers. Done
  rows carry none. Nobody sets one by hand.
  - `needs-data`: an open `mart:` stage or column addition blocks it
  - `needs-cube`: otherwise, an open `cube:` or `view:` stage blocks it
  - otherwise a `Needs: data` or `Needs: cube` line in the row's notes sets it:
    triage for a row whose work nobody has made a task for yet
  - no tag: nobody has worked out what it needs yet
- `validated`: the latest verdict in `~/asana-sync/validation/latest.json` is
  `pass`. Internal only; the status page ignores it. Every other verdict leaves
  the tag off, and each gap it found is a subtask under the row, linking its
  follow-up.
- The sync strips every other tag from rows, apart from `measure` and
  `dimension`.
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
   (`needs-cube`) until it exists.

Existing named measures are never removed just because they are slices; rule 1
only stops new pure-slice members.

## Structure

- One Asana task per table (named for the table), with stage subtasks `mart:`
  (only if the table is new), `cube:`, `view:` (facts only; dims join into the
  fact's view), then column additions.
- Each dashboard task holds its measure rows and its checklist steps.
- A dimension row is a subtask of the table its column comes from, one per
  column, never a copy per dashboard. Its notes carry `Use:` (how dashboards use
  it), `Used by:` (links to every dashboard task that slices or filters by it;
  this line is what makes it a dimension row and puts it on those dashboards'
  status), an optional `Needs:` line, and `Where it lives:` last
  (`<view>.<member>`, the name Cube exposes, e.g. `locations_location_name`). A
  Tableau-only field gets no row.
- Dependencies: `mart` blocks `cube` blocks `view`; a row is blocked only by the
  stage or addition that builds its own member. A table task blocks every
  dashboard its dimension rows name in `Used by:`; the sync adds those links.
  The table, not each column, blocks the dashboard because Asana caps a task at
  30 dependencies plus dependents. A dashboard is blocked by nothing else.
- Each domain section has an `Open Issues — <Domain>` parent task (Assessments'
  is named `Open Issues`). Every follow-up a validation files sits under it.
- Shared section = conformed dims: calendar and org, the student spine, the
  staff spine.
