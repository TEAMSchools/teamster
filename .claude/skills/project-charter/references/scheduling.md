# Scheduling

Phase 3. The date rules live once, in the docstring of
`scripts/schedule_dates.py`; this file covers getting the inputs in and the
output back into the doc.

## Read the breaks tab

One Sheets `get_values` call on the whole tab named in `ids.md`, range
`'<tab>'!A1:H80`. Space it from any other Sheets call in the same minute; the
per-minute read quota is small. The tab holds a federal-holidays list first and
the breaks table below it, headed
`Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson`. Write the breaks
table only, from its header row down, to a scratchpad file named
`breaks-<school year>.csv` with the headers unchanged. Forms the script accepts
in `Date`: `11`, `25-27`, `23-27`, `Dec 21 - Jan 1`, `29-2 (Apr)`. A blank
`Month` continues the row above. A region cell is a closure only when it is
exactly `Yes`; `No`, `-` and blank are not. A row short of a region column is
fine.

## Write the plan rows

`<scratchpad>/plan-<project>.csv` with headers
`workstream,name,kind,duration_weeks,after,override`:

- `workstream`: the charter's lane, in the charter's order.
- `name`: unique across the file; it is what `after` points at.
- `kind`: `milestone` or `task`.
- `duration_weeks`: working weeks, whole numbers, at least 1.
- `after`: the `name` this row follows, or blank to start at the project start.
  Workstreams run in parallel by default; a cross-workstream dependency is one
  `after`.
- `override`: an ISO date that replaces the computed one. Followers shift with
  it.

The last row is the close milestone with the lessons-learned session.

## Run

```bash
uv run python .claude/skills/project-charter/scripts/schedule_dates.py \
  --breaks <scratchpad>/breaks-<year>.csv --school-year <YYYY> \
  --regions Newark,Camden --start <YYYY-MM-DD> \
  --plan <scratchpad>/plan-<project>.csv --end <charter target end>
```

`--school-year` is the year the school year starts in. `--regions` is the
charter's scope; a region outside it never blocks a week. The output is a
markdown table with `rule` (which rule placed the date: `friday`,
`closed friday -> thursday`, `override`) and `note`. A `note` of
`unverified: calendar not published` means the date is past the last closure in
the tab; tell the user to re-run phase 3 for those rows when the next year's
sheet exists. A final line names any row due after `--end`; move that work or
ask for a new end date before writing the plan into the doc. Exit code 2 with a
message on stderr means a plan row is wrong (an `after` naming no row, a
duplicate name) or the breaks CSV has an unparseable row; fix the CSV and
re-run.

## Override

When the user moves a date, put it in the `override` column and re-run; do not
edit the output table by hand. The output's `note` column, `override` included,
goes into the work plan's note column so the reason survives.

## Write back

Three writes into the charter doc, in this order:

1. Template 2, the work plan table: one row per output row, in output order,
   with milestone or task, owner from the charter, due date, status blank.
2. A table titled `Schedule inputs` straight after Template 2, holding the plan
   CSV as columns, so a later re-run starts from the same rows and dependencies.
3. Template 1's milestone table: replace each month-level target with the
   milestone's exact date.
