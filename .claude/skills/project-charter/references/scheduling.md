# Scheduling

Phase 3. The date rules live once, in the docstring of
`scripts/schedule_dates.py`; this file covers getting the inputs in and the
output back into the doc.

## Read the breaks tab

One Sheets `get_values` call on the whole tab named in `ids.md`, range
`'<tab>'!A:H` (whole columns, so a row added at the bottom is never missed).
Space it from any other Sheets call in the same minute; the per-minute read
quota is small. The tab holds a federal-holidays list first and the breaks table
below it, headed `Month,Date,Day,Holiday/Event,Newark,Camden,Miami,Paterson`.
Write the breaks table only, from its header row down, to a scratchpad file
named `breaks-<school year>.csv` with the headers unchanged. The scratchpad does
not always survive between phases; if the file is gone at phase 3, export it
again rather than rebuilding it from memory. Forms the script accepts in `Date`:
`11`, `25-27`, `23-27`, `Dec 21 - Jan 1`, `29-2 (Apr)`. A blank `Month`
continues the row above. A region cell is a closure only when it is `Yes` (case
matters; surrounding spaces do not); `No`, `-` and blank are not. A row short of
a region column is fine. A break split across rows (a two-day row plus a one-day
row) still blocks its week: the script counts closed days per region across
rows. Closed days in different regions never add up, so a week where two regions
together close four days still counts as a working week and its due date walks
back to the first open day, Monday included; override it if the team is in fact
out.

## Write the plan rows

`<scratchpad>/plan-<project>.csv` with headers
`workstream,name,kind,duration_weeks,after,override`:

- `workstream`: the charter's lane, in the charter's order.
- `name`: unique across the file; it is what `after` points at. No `|` in a name
  or workstream; the output is a markdown table.
- `kind`: `milestone` or `task`.
- `duration_weeks`: working weeks, whole numbers, at least 1.
- `after`: the `name` this row follows, or blank to start at the project start.
  Workstreams run in parallel by default; a cross-workstream dependency is one
  `after`.
- `override`: an ISO date that replaces the computed one. Followers shift with
  it.

The governance and handoff rows are standard rows, in a `Governance` workstream
that phase 4 maps onto the Asana template's standing tasks rather than a section
of its own: Charter signed (milestone, override to the signing date), Kickoff
(milestone, first week), Close and lessons learned (milestone, `after` the last
delivery milestone), and Name the owner after close, Help article or training,
Comms to affected staff (tasks, also `after` the last delivery milestone, so
they share the close milestone's week). The names match the template's exactly.

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
edit the output table by hand. The reason survives through the `Schedule inputs`
table below, which carries the output's `rule` and `note` columns. An override
on a weekend, a closed day, in a blocked week, before the project start, or on
or before the row it follows is placed as given and its note says which; show
that note to the user before writing the plan.

## Write back

Three writes into the charter doc, in this order:

1. Template 2, the work plan table, in the template's four columns: one row per
   output row, in output order, with milestone or task, owner from the charter,
   due date, status blank. The `Workstream N` and `MILESTONE N` rows are one
   cell merged across the four columns, so their owner and date go inside the
   label text, `MILESTONE 1: <name> (<owner>, <date>)`; an insert into one of
   their hidden cells lands mid-label. Task rows have four real cells. The
   template has two workstreams with three, three and two task rows; insert or
   delete rows to fit before filling, from the bottom up, then read the doc
   again for positions. Template 2 has no column for the rule or the note; they
   live in the next table.
2. A table titled `Schedule inputs` straight after Template 2: the plan CSV's
   columns plus `due`, `rule` and `note` from the output, one row per plan row.
   This is where the user sees which rule placed a date and which dates are
   `unverified`, and where a later re-run starts from.
3. Template 1's milestone table: replace each month-level target with the
   milestone's exact date.
