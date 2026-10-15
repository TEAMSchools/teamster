# Cube validation redesign: frozen rows first, then cells

Status: sections approved in conversation 2026-10-15; awaiting review of the
written spec. Refs #5856. Supersedes
`2026-10-09-cube-validate-tableau-truth-design.md`. #5917 (quick check) was
closed as not planned in favor of this design.

## Goal

Before a dashboard moves to Cube, show that every number a person can see on it
comes out the same from Cube, or say why it doesn't and who fixes it.

- **Users:** data-team analysts working in Claude Code. Claude runs the steps;
  the analyst approves the cut list, the mapping, every cause, and the hand
  checks.
- **Success:** someone without this design's history can validate a dashboard,
  and the tool never blames Cube for an error of its own.
- **First target:** the Attendance Dashboard (exposure `attendance_dashboard`,
  LSID `87c13e78-a912-40a4-95dd-33248fc1cbd3`).
- **Out of scope:** filing issues, Asana sync and `latest.json` (findings are
  held until the tool is trusted; filing gets its own design), build mode, the
  weekly run (#5842), and rows missing from both sides.

## Why a redesign

Evidence from the DDI Suite run of 2026-10-14 and its retro experiments:

- **Time:** about 5.6 hours, about 4.2 of them waiting on Cube. Queries ran one
  at a time at 8 to 11 s each, every measure was asked twice, and explain asked
  Cube again.
- **Clocks:** 26% of mismatches crossed clocks: the extract, Cube at compare and
  Cube at explain each read different data.
- **The tool's own SQL:** 28% of mismatches stayed unjudged because the tool's
  rewrite of Tableau formulas could not reproduce Tableau.
- **Cost:** the run caused a BigQuery billing spike (confirmed 2026-10-15).
- **What worked:** a single row-level reconciliation of the dashboard table
  against Cube's fact put every row in exactly 1 bucket with 3 causes. Parallel
  Cube queries (8 workers) ran 4.6 times faster with identical answers.

## Rulings that bind this design

- Start fresh. Old checks, snapshots, verdicts and scripts are not constraints.
  A piece is reused only by deliberate choice, named below.
- Freeze both sides and compare like for like. No live SQL and no live Cube
  during comparison or explanation.
- Go through Cube. Fact-table SQL never stands in for Cube.
- Aggregate queries carry `count_students`. Attendance has no pre-aggregations;
  whether checks on a dashboard with rollups should use them is decided per
  dashboard, with cost shown by preflight.
- Cuts exercise dashboard logic only, with no drill-down levels.
- Timing guidance is dashboard-specific.
- Data findings are held until the tool is trusted.

## Unit of a run

1 run checks 1 data source of 1 dashboard against its Cube view or views.

- Cube may supply more than 1 view for one source when it splits by grain. For
  Attendance, `student_attendance_enrollment_daily_view` supplies rows and
  cells; `student_attendance_enrollment_periods_view` adds cells for period
  measures such as chronic absence.
- The report lists the dashboard's other data sources and their sheets with a
  reason: "no Cube counterpart" or "separate run".
- A sheet that blends 2 data sources is reported "blended, not checked".
- Attendance needs 1 run: `rpt_tableau__attendance_dashboard`. The comm log and
  interventions sources have no Cube counterpart.

## Attendance timing (New York time)

Re-check these before relying on them; they come from a few days of job history.

- **Extract refresh:** 6:00 AM and 3:00 PM (Dagster ticks, Oct 13 to 15).
  `docs/reference/automations.md` lists only 3:00 PM and is out of date.
- **Cube's facts:** rebuilt about 6:15 AM and 3:05 PM.
- **Capture window:** about 3:30 PM to 6:00 AM. Inside it the extract and Cube's
  facts come from the same afternoon build. The 6:00 AM extract is built before
  the 6:15 AM fact rebuild, so morning hours never pair.
- **Years:** the dashboard model covers July 1 of last school year to today.
  This year is captured every run. Last year (2025-26) is captured once, because
  its rows are frozen at the source, and again only when its logic changes. It
  rolls off the dashboard in July.

## Run shape

One command, 4 phases. Only capture touches Tableau, Cube or BigQuery for real.

1. **Preflight** (free, about 1 minute)
   - Compile every planned Cube query through `/sql` and dry-run it on BigQuery.
     Stop if the total bytes exceed the dashboard's `cost_cap_gb`.
   - Confirm the extract's last refresh is the expected one and the time is
     inside the window.
   - Record the clock map: the last-modified time of every base table under both
     sides, from `__TABLES__` on tables, never views.
   - Stop if the workbook reads a published data source instead of an embedded
     extract, or if an earlier review copy still exists.
2. **Capture** (about 15 to 25 minutes, the only phase that costs money)
   - Tableau side, then Cube side (below).
   - Re-check the clock map. A base table that changed between the extract
     refresh and the end of capture marks the snapshot "clock risk" and names
     the table.
   - Write the manifest: times, row counts, checksums, Cube's school scope.
3. **Analysis** (minutes, snapshot only)
   1. Rows layer.
   2. Cells layer.
   3. Hand-check list.
4. **Report**: trust verdict first, held findings second.

Analysis and report re-run on the same snapshot for free. Changing a cause or a
cut definition never needs a new capture.

## Capture

### Tableau side

- Download the live workbook with its extract (`.twbx`). It yields the `.hyper`
  rows, the `.twb` formulas, filters and groups, and the extract refresh time.
  Reused deliberately: the old `_download` and `.hyper` reader.
- Publish a review copy to TEMP-CB from that same file, then export the approved
  cuts from it. The copy's extract is the downloaded snapshot and never
  refreshes, so exports cannot race the next extract refresh. Reused
  deliberately: the old Tableau session handling (lost-token waits, quiet
  minutes), because Dagster's refreshes share the token.
- Filter proof: a cut whose export equals the default view's, when the `.hyper`
  says its filter should change the numbers, is "filter ignored" and never
  counts as data.

### Cube side

- **Rows:** the daily view, ungrouped, this year, split by month and school.
  Columns: student, day, school, the attendance fields, and every dimension a
  cut filters on. Filter on `attendance_date`, which prunes the fact's
  partitions (a dry run measured 47 MB for this year against 1.87 GB
  unfiltered).
- **Completeness:** each part gets 1 aggregate query counting its rows. Captured
  rows must equal that count. A part that returns exactly the row limit is split
  again.
- **Aggregates:** 1 query per cut and measure, each with `count_students`.
- **Concurrency:** 8 workers.
- **Stamps:** every answer keeps its own `lastRefreshTime`. An answer older than
  the fact's last build is asked once more, then fails capture.
- **Scope:** Cube rewrites every query to the caller's schools. The manifest
  records that list.

### Storage

`~/.cache/cube-validate/<dashboard>/<snapshot>/`: the downloaded extract, Cube's
rows and answers written to a `.hyper` file of their own with the Hyper API, the
exports, and `manifest.json`. Student-level and local only. Hyper is already
required to read the extract, so the snapshot adds no dependency.

## Rows layer

- Full outer join, in Hyper with both `.hyper` files attached, of the extract's
  rows (`student_number`, `calendardate`, school) and Cube's rows
  (`lea_student_identifier`, `attendance_date`, school). School is in the key
  because a student can hold 2 schools on 1 day.
- Every row gets exactly 1 bucket:

  | Bucket         | Meaning                                             |
  | -------------- | --------------------------------------------------- |
  | match          | Same key, same values on every compared column      |
  | value differs  | Same key; each differing column counted on its own  |
  | dashboard only | Key missing from Cube                               |
  | Cube only      | Key missing from the dashboard                      |
  | outside scope  | School outside Cube's recorded scope for the caller |

- The last 4 split further by cause. A cause in the config has an id, a
  plain-language description, a SQL predicate over the joined row (Hyper's
  Postgres-style dialect), and an owner (`cube`, `dashboard`, `source`,
  `undecided`).
- Causes must not overlap. A row matching 2 causes is a tool error. No order
  decides anything.
- Rows no cause claims are "unexplained", listed by key.
- A cause is added only with this snapshot's numbers: rows it claims and what
  stays unexplained. Causes are never carried over unmeasured.
- The first run starts with no causes. Leads to measure, not assume: Miami
  (Focus) tardy and suspension flags are null on the Cube side, and the
  dashboard joins enrollments with an inclusive `exitdate`.

## Cells layer

### Cuts

The tool drafts the cut list from the `.twb`; the analyst approves it before
capture. Each cut tests 1 piece of dashboard logic:

- the default view
- each filter card at 1 non-default value
- each parameter value that changes a calculation
- each group or bin
- each click action, once

No drill-down levels. Sheets with a name column are excluded. Cuts with
identical exports are flagged as filter ignored or as duplicates to drop.

### Mapping

Approved once per dashboard:

- Each exported column maps to a Cube member.
- Each filter maps to a Cube filter and to a row predicate that selects the
  cut's rows from the rows layer.
- The tool translates filters only, never formulas.
- Predicate proof: in the `.hyper`, each cut's predicate must select the number
  of students the dashboard shows for that cut. A mismatch makes the cut
  "mapping unproven".

### Verdicts

| Verdict             | When                                                                                      |
| ------------------- | ----------------------------------------------------------------------------------------- |
| pass                | Numbers match at Tableau's display precision and the cut's rows all match                 |
| coincidental match  | Numbers match but the cut's rows differ                                                   |
| row gap             | Rows differ inside the cut; lists each bucket with row and student counts                 |
| formula gap         | All rows in the cut match but the numbers differ; shows the `.twb` formula and Cube's SQL |
| filter ignored      | The cut's filter did not apply                                                            |
| mapping unproven    | The cut's predicate failed its proof                                                      |
| no Cube counterpart | No Cube member for the column                                                             |

- When rows and formula both differ in a cut, the cell is a row gap. A measure's
  formula is tested by the cuts whose rows all match. If none exists, the report
  says that measure's formula is untested.
- Cube's compiled measure SQL comes from preflight's `/sql` calls.
- The last 3 verdicts are never Cube findings.

## Trust

The tool is trusted when all 3 hold. Data findings never affect this.

1. **Unit tests pass.** Planted gaps live in tests, not in runs: tiny synthetic
   rows and cells (a handful of students, 2 schools, a few days) with a known
   gap and the exact expected buckets and verdicts. Cases include deleted rows,
   flipped values, a moved school, duplicates, and a shifted cell.
2. **Every run's invariants hold:**
   - capture completeness: each Cube part's rows equal Cube's count for it
   - row totals balance: every captured row lands in exactly 1 bucket
   - filter proof: an ignored filter never counts as data
3. **Hand checks from the first Attendance run agree.**
   - 10 to 15 entries covering every verdict and bucket the run produced, plus a
     few random passes.
   - Tableau side checked in the review copy, which shows the snapshot's
     extract, before the copy is deleted.
   - Cube side compared with the captured value and its `lastRefreshTime`, the
     same evening or against the snapshot only.
   - Row entries add a source-system lookup (PowerSchool or Focus), which says
     which side is right.
   - The analyst marks each entry agree or disagree in a local results file,
     which the trust verdict reads.

## Outputs

- `report.md`: trust verdict, invariants, row buckets by region, month and
  cause, cell verdicts, excluded sheets with reasons. Aggregate counts only, and
  any count under 10 shows as "<10", so it can go to `#data_team`.
- `hand_checks.md`: names student and day keys, so it stays local.

## Privacy

- Committed: the config (schools, filters, mapping, causes). Never a person's
  name.
- Local only: the snapshot, row keys, hand checks.
- Never sent to git, GitHub or agent output.

## Failures

| Phase     | Stops when                                                                    | Recovery                                                                     |
| --------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Preflight | Outside the window, over the cost cap, published data source, old review copy | Fix and rerun; nothing spent                                                 |
| Capture   | Tableau token lost or Cube connection dropped                                 | Retry the part                                                               |
| Capture   | Stale answer after 1 re-ask, or a completeness mismatch                       | Snapshot fails, naming the parts                                             |
| Capture   | Interrupted                                                                   | Rerun resumes, keeping finished parts, if in the window and clocks unchanged |
| Analysis  | Overlapping causes or unbalanced totals                                       | Report stops with the tool error                                             |

Data never makes analysis fail.

## What gets built

- New package `scripts/cube_validate/`, one module per job: `config`,
  `preflight`, `capture_tableau`, `capture_cube`, `rows`, `cells`, `report`.
- Replaced: `scripts/cube_validate.py`, `scripts/cube_validate_snapshot.py`,
  their tests, and `checks/ddi_suite.yml`. The branch never shipped; git history
  keeps them.
- Reused deliberately: the `.twbx` download, the `.hyper` reader, Tableau
  session handling, the Cube client's per-thread connection and retry.
- Rewritten: `.claude/skills/cube-dashboard/SKILL.md`.
- New: `.claude/skills/cube-dashboard/checks/attendance_dashboard.yml` with
  `cost_cap_gb`, window, cuts, mapping and causes.

## Done when

1. The unit tests with planted gaps pass.
2. A first Attendance run finishes inside the window in under about 45 minutes,
   under the cost cap, with every invariant holding.
3. The analyst's hand checks agree.
4. Someone without this context can run it from `SKILL.md`.
