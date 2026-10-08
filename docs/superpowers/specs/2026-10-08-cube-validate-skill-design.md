# cube-dashboard skill, validate mode: design

Status: sections approved in conversation 2026-10-08; awaiting review of the
written spec. Refs #4314.

## Goal

Check that what Cube returns for each shipped measure matches what the live
Tableau dashboard shows, at every grain and filter people use, and report
matches and mismatches back to the Asana project "Data Marts + Semantic Layer".
The first run is an audit of the measure rows already tagged `cube-covered`.

One skill, `cube-dashboard`, with two modes:

- **Validate** (this spec, in full): compare Cube with Tableau for a dashboard's
  done rows.
- **Build** (its own spec later): work a dashboard's blocking table tasks in
  order (mart, cube, view, column additions). Its last step writes each finished
  row's check entry and runs validate, so a row counts as built only once it
  passes. This spec defines only the interface build mode plugs into.

Model case: #5692, fixed by #5716. `student_assessment_scores_view` dropped
about 1 in 10 state test scores because of an upstream mart join. STAT in
Tableau was right; Cube was short.

## Decisions

- **Results:** one Asana comment per row, plus a `mismatch` tag that `sync.py`
  applies and respects (it stops auto-ticking a tagged row).
- **Tolerance:** counts match exactly; rates match within 0.1 percentage point.
  Every gap is reported with its size, even inside the band.
- **Tableau side:** the row's Tableau formula as SQL on its live
  `kipptaf_tableau.rpt_tableau__*` table, with the dashboard's hard filters.
  Rendered `get-view-image` checks confirm the translation. Rejected: rendered
  images only (rounded, slow, extract-timing skew) and the workbook's `.hyper`
  extract (same translation work, stale snapshot, catches nothing more).
- **Grains:** every grain and filter the dashboard's sheets use, derived from
  the `.twb` shelves, not just the top-line number. A total can match while a
  region or school is far off. Filter dimensions are checked one at a time, not
  crossed. A row passes only if every cell passes.
- **Pilot:** the Attendance Dashboard's 7 done rows, then the other
  `cube-covered` rows.
- **Out of scope:** Anthony's "Matches within tolerance" checklist item, until
  he agrees.

## Section 1: pieces and data flow

### Files

- `.claude/skills/cube-dashboard/SKILL.md`: the runbook Claude follows.
- `.claude/skills/cube-dashboard/checks/<dashboard>.yml`: one entry per done
  row, reviewed in the PR. Holds the Asana row gid, the Cube view and member,
  the check kind (`count` or `rate`), the truth SQL on `rpt_tableau__*` with a
  `{grain}` placeholder, the dashboard's hard filters, the grain list (derived
  once from the `.twb`), and the Tableau views plus `viewFilters` for renders.
- `scripts/cube_validate.py`: runs one dashboard's checks. For each row and
  grain it runs Cube `/load` and BigQuery, joins cell by cell, applies the
  tolerance, and writes the report and `latest.json` (Section 3). Runs under a
  throwaway pytest for the Cube secret. A script, not MCP calls, because about
  100 rows times about 10 grains returns thousands of cells: too much to pass
  through the session.

### Interface for build mode

Build mode (later spec) uses validate through two things only: it appends a
row's entry to `checks/<dashboard>.yml`, then runs
`scripts/cube_validate.py <checks file> --rows <gid>`. A row it built is done
only when that run returns `pass`.

### Flow for one dashboard

1. Read the dashboard's done rows from Asana.
2. Author a check entry for any row without one. This is the judgment step
   (Tableau formula to SQL); the user reviews new entries.
3. Run the script. Both sides use the same window: July 1 of the current
   academic year through yesterday.
4. Render each tab once per region and at the worst cells; compare to the
   report.
5. Post one comment per row: verdict, window, grains checked, worst cell per
   grain.
6. The user runs `sync.py`. A new step reads `latest.json`, adds or removes the
   `mismatch` tag, and skips auto-ticking any row tagged `mismatch`.

## Section 2: check entries and grains

### One checks file per dashboard

`checks/attendance_dashboard.yml` (illustrative; values are the real member and
column names):

```yaml
dashboard: attendance_dashboard
task_gid: "1213823788919470"
workbook_luid: 87c13e78-a912-40a4-95dd-33248fc1cbd3
table: kipptaf_tableau.rpt_tableau__attendance_dashboard
view: student_attendance_enrollment_daily_view

# Tableau field -> Cube member -> rpt_ column. Shared by every row.
dimensions:
  date: { cube: attendance_date, sql: calendardate }
  academic_year: { cube: dates_academic_year, sql: academic_year }
  region: { cube: regions_region_name, sql: region }
  school: { cube: locations_abbreviation, sql: school_abbreviation }
  grade_level: { cube: grade_level, sql: grade_level }
  team: { cube: null, sql: team } # no Cube member: grain reported, not compared

# The dashboard's own hard filters, applied on both sides.
hard_filters:
  - { dim: region, values: [Camden, Newark, Paterson] }

rows:
  - row_gid: "1214703929266204"
    name: "# Tardy"
    metrics:
      - { cube: count_tardy_days, kind: count, sql: "sum(is_tardy)" }
    grains: # from the .twb shelves of every sheet that uses the measure
      - []
      - [region]
      - [region, school]
      - [region, school, grade_level]
      - [region, team]
    renders:
      - { view: 2995637c-c212-4909-a9e8-db3e6b533acc, by: region }
```

- A row can carry several metrics. Truancy, for example, has `pct_truant` and
  `count_truants`.
- Some views need their own `view:`/`table:` override per row, for example the
  periods view for chronic absence.
- A `rate` metric's SQL returns the numerator and denominator separately. That
  way a cell's rate and its size both reach the report.

### Deriving the grains

1. Download the workbook once per dashboard (the `tableau-workbook-xml` skill's
   download path).
2. A helper in `scripts/cube_validate.py` lists every worksheet that sits on a
   published dashboard (hidden building-block sheets included) and references
   the measure's field, with the dimensions on its rows, columns, and filters
   shelves.
3. Each worksheet's rows-plus-columns set is one grain. Each filter dimension is
   one more grain, added to the sheet's base grain one at a time.
4. Claude writes the deduplicated list into `grains:`, and the user reviews it
   with the rest of the entry. The grains are re-derived only when the workbook
   changes.

### Dimensions with no Cube member

A grain that uses a dimension with `cube: null` (homeroom `team`, for example)
is reported as **not comparable**: a coverage gap, not a mismatch. It does not
fail the row, and the report lists it so the gap catalog can pick it up.

## Section 3: run, report, sync, errors, tests

### The run

- `scripts/cube_validate.py <checks file> [--rows <gid,...>]` runs every row and
  grain in the file.
- One Cube `/load` per (view, grain) carries every metric on that view, so a
  dashboard costs one query per view-grain pair, not one per metric.
- Cube auth mints the same HS256 JWT as `src/cube/mcp/server.py` (`email`,
  `iat`, `exp`, signed with `CUBE_API_SECRET`) as the requesting user. BigQuery
  uses ADC with `google-cloud-bigquery`.
- Window on both sides: July 1 of the current academic year through yesterday.
- **Scope guard first.** Before comparing, run one `count_students` per value of
  the hard-filter dimension (each region). If any comes back 0, the viewer's
  Cube scope is narrower than the dashboard's, so the run stops instead of
  reporting false mismatches.

### Comparing cells

- Full outer join on the grain's dimension values. A cell present on one side
  only is a mismatch; that is the #5692 shape.
- Null dimension values form their own cell on both sides.
- `count`: equal or fail. `rate`: |Cube − SQL| ≤ 0.001 (0.1 point) or fail.
- On a failed cell, the script also calls Cube `/sql` for that query and records
  whether it hit a pre-aggregation. A rollup that has not refreshed is a
  different fix from a mart gap.

### Outputs

- `~/asana-sync/validation/<date>-<dashboard>.md`: per row, per grain: cells
  checked, cells out of tolerance, the 5 worst cells with both values and the
  cell size. Not-comparable grains are listed separately.
- `~/asana-sync/validation/latest.json`: one entry per row gid, merged across
  dashboards: `pass` / `fail`, run date, worst cell. This is the file `sync.py`
  reads.
- Both stay outside the repo (they hold per-school numbers and change every
  run).

### Asana comment (one per row, posted by Claude)

```text
Cube vs Tableau check, 2026-10-08: FAIL
Window: 2026-07-01 to 2026-10-07. 5 grains, 214 cells, 3 out of tolerance.
Worst: region x school, Newark / <school>: Cube 1,204, Tableau 1,377.
Not comparable: region x team (no Cube member).
Report: ~/asana-sync/validation/2026-10-08-attendance_dashboard.md
```

Cells under 10 students show as "small cell" with no values. Aggregates only; no
student-level rows ever reach Asana.

### `sync.py` change (user-run, outside the repo)

A new step reads `latest.json`, adds the `mismatch` tag to `fail` rows and
removes it from `pass` rows, skips auto-ticking any row tagged `mismatch`, and
lists done-but-`mismatch` rows in its report. Done rows stay done.

### Errors

- Cube or BigQuery error on one grain: that grain is reported as `error` with
  the message, and the row's verdict is `incomplete`, not `pass`.
- A check entry that names a member missing from the view: the row is
  `incomplete`, and the run continues.
- Renders that disagree with the warehouse SQL: Claude flags the check entry's
  SQL for review in the report; the row is `incomplete` until it is fixed.

### Tests

- `tests/scripts/test_cube_validate.py`, no live calls: the tolerance rules, the
  outer-join cell compare (including a one-sided cell and a null cell), the
  cancelling-errors case (total matches, a school is off: row fails), the scope
  guard, and grain derivation from a small `.twb` fixture.
- Acceptance: the Attendance pilot runs end to end, and its report and comments
  are reviewed with the user before widening.

### Open item for the plan

Whether `tests/conftest.py`'s secret loading provides `CUBE_API_SECRET`. If it
does not, the user runs the script in their own terminal.

## Revision 2026-10-08: flag missing Cube members

Requested by the user after the Attendance checks review: any discrepancy that
comes from a member Cube lacks must be flagged as such, so the member gets
added, rather than reading as a bug.

- A metric whose Tableau definition uses a field Cube lacks lists it under
  `missing_members:` and carries the same SQL without that logic (`sql_without`,
  or `num_without`/`den_without`). A cell that fails against `sql` but matches
  the `_without` variant is **explained** by the missing member, not counted as
  out of tolerance.
- A grain on a dimension with no Cube member stays not comparable, and its
  dimension is listed as a missing member that blocks that grain.
- Row verdicts, strongest first: `fail` (any unexplained gap), `incomplete` (a
  grain errored), `missing_member` (every gap is explained), `pass`. A row whose
  only missing members block grains, with no explained gaps, can still pass.
- The comment, report and `latest.json` list each missing member with the cells
  it explains and the grains it blocks.
- `sync.py` reopens a `missing_member` row: it unticks it, tags it
  `cube-partial`, and never auto-ticks it while `latest.json` says so. `fail`
  keeps the `mismatch` tag and stays done.

## Revision 2026-10-08: compare against the dashboard's extract

Reverses the "Tableau side" decision above, at the user's request, after the
Attendance pilot. The warehouse `rpt_tableau__*` model is a live view, while
Cube reads a fact table built once each morning and the dashboard serves an
extract refreshed soon after. Comparing Cube with the live view mixed real gaps
with attendance corrections entered since the morning build (`# Absences` moved
by 30 between two runs an hour apart).

- The truth side is the dashboard's own extract: the run downloads the workbook
  with its extracts, unpacks the named datasource's `.hyper` file, and runs each
  grain's SQL there. Check SQL stays in BigQuery dialect; `sqlglot` translates
  it to Hyper's PostgreSQL dialect.
- A timing guard reads the extract's refresh time (the workbook's `updated_at`)
  and the Cube fact's build time (`cube_source_table` in BigQuery `__TABLES__`)
  and stops when they are more than 60 minutes apart. Both times appear in the
  report and in every comment.
- The window ends the day before the extract refresh, in local time.
- The checks file names `extract: {workbook_luid, datasource}` and
  `cube_source_table` instead of `table`. The warehouse path is removed.
- `tableauhyperapi` is not a project dependency; the run adds it with
  `uv run --with tableauhyperapi`.

## Revision 2026-10-08: a fix digest instead of long comments

Requested by the user after reading the first comments: an analyst and Claude
must be able to take a validation result and know what to edit in a cube or a
model.

- Each run writes `<date>-<dashboard>-fixes.md`. "Add to Cube" lists each
  missing member that explains gaps, merged across rows, with what it is, where
  it lives and a suggested edit, from the checks file's `members:` notes.
  Dimensions that only block grains follow as a lower-priority list.
  "Investigate" lists each row's gaps nothing explains: the total, the worst
  grain, a breakdown by the metric's `diagnose_by` field (run on the SQL without
  the missing members' logic), and the dashboard and Cube definitions side by
  side, including the measures a derived Cube measure uses.
- Each fix becomes one Asana task (a column addition on its table task, or a
  "Decide:" task for a definition mismatch), linked as a blocker of the rows it
  affects. The digest is posted once on the dashboard's task; each row's comment
  shrinks to its verdict and links to its fix tasks.

## Revision 2026-10-08: reopen on any missing-member gap

Found when the user asked why rows blocked by the out-of-district fix were still
ticked. Reopening only `missing_member` rows (every gap explained) left a row
with a missing member plus another bug ticked. Now any row a missing member
causes part of the gap in reopens: `latest.json` lists those members as
`reopen_for` (they explain cells, or the dashboard's total moves without their
logic), and `sync.py` unticks the row and tags it `cube-partial`. A `fail` also
keeps its `mismatch` tag. Members that only block grains still do not reopen.
