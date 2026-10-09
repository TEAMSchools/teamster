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

## Revision 2026-10-08: Tableau constructs that change what a sheet shows

Found on STAT: the grade-range group never reached the checks, and the grain
proposer missed discipline hidden in field copies and parameter-driven columns.
The user asked for groups to be handled, and for every other way Tableau can
make a sheet's number differ from the check SQL to be found.

### What the 2 workbooks use

| Construct                                          | STAT    | Attendance |
| -------------------------------------------------- | ------- | ---------- |
| Groups (`categorical-bin`)                         | 4       | 3          |
| Plain copies of a field                            | 19      | 8          |
| Calculations that read a parameter                 | 33      | 13         |
| Drill paths (hierarchies)                          | 4       | 0          |
| Sets and other datasource groups                   | 11      | 40         |
| Columns with aliases                               | 24      | 16         |
| Sheets with quick table calculations               | 28      | 3          |
| FIXED level-of-detail calculations                 | 21      | 5          |
| Context filters / exclude filters                  | 59 / 54 | 7 / 11     |
| Totals or subtotals                                | 44      | 29         |
| Calculations using viewer functions (`ISMEMBEROF`) | 3       | 0          |
| Fiscal year start set on the datasource            | no      | July       |

Neither uses numeric bins, blends, top-N filters or extract filters; detection
covers them anyway.

### Rule: nothing is skipped silently

`grains` inventories every construct on each sheet that shows a checked measure.
The checks file accounts for each one: handled (a dimension, a filter or the
metric SQL reproduces it) or listed under the row's `not_checked:` with what it
is, why, and the sheets. Each run re-reads the workbook and marks a row
`incomplete` when a construct on its sheets is in neither place, so a workbook
edit after authoring cannot slip past either. `not_checked:` items do not fail a
row; the digest lists them under "Not checked" and the row comment says how
many.

### Handling, by construct

- **Groups.** A dimension may declare
  `group: {of: <sql>, bins: {<label>: [values]}}`; the tool writes the CASE.
  Values in no bin keep their own value (no workbook defines an Other bin;
  confirm with 1 render before relying on it). Each group also takes
  `kind: relabel` (codes rolled into coarser buckets) or `kind: rule` (a
  definition, such as speech-only IEP counted as no IEP). On the Cube side it
  maps to a member whose values equal the bin labels, or `cube: null`. The
  digest lists rule groups as decisions, relabels as members to add.
- **Numeric bins.** Translated to `floor(x / size) * size`; Cube side as for
  groups.
- **Plain copies.** Resolved to the source field in grains and formulas.
- **Parameter-driven fields.** A CASE on a parameter is expanded: each branch is
  its own grain (or its own measure, when the parameter swaps measures), so the
  STAT goals sheet yields one grain per level.
- **Drill paths.** Every level of the path is a grain on the sheets that use it,
  not only the level on the shelf.
- **Sets.** A set or combined field used as a filter changes the population. One
  that encodes a rule (attendance's "Exclude OOD") is a missing member, as out
  of district already is. Action, tooltip and highlight groups come from viewer
  clicks and are ignored.
- **Aliases.** They change labels, not numbers. Renders show the alias, so the
  render step maps it back to the value. On Measure Names an alias can show one
  field under another's name (STAT's "2024 Goal" is the field "2023 Goal
  (copy)"), so `grains --measure` matches captions and aliases and prints the
  field it resolved to.
- **Table calculations.** Percent of total, difference, rank and running totals
  are computed from the table on screen, not at the grain. The check compares
  the base aggregate and lists the sheet under `not_checked:`.
- **Level-of-detail calculations.** FIXED ignores every filter except context
  filters; INCLUDE and EXCLUDE respect them. `grains` prints each sheet's
  context filters beside the formula, and a FIXED metric applies only those
  inside the calculation.
- **Filters.** `grains` prints each filter with its mode: exclude (`NOT IN`),
  null members (`%null%`), context. The skill writes `hard_filters` and
  `truth_filters` from that, not from the field name alone.
- **Totals.** A total is the measure at the coarser grain, which the grain list
  already holds. A total set to sum or average the rows of a non-additive
  measure is listed under `not_checked:`.
- **Viewer functions.** `ISMEMBEROF` and `USERNAME` make the sheet differ by
  viewer. The run uses a network identity on the full extract, so these are
  listed under `not_checked:` with the groups they test.
- **Fiscal year and week start.** A date part on a shelf follows the
  datasource's fiscal year start, so the dimension SQL has to as well.

### To confirm in the plan

- Values outside every bin keep their own value (1 render of a grouped sheet).
- Where the `.twb` records a total's aggregation (sum of rows vs the measure at
  the total).
- Whether the fiscal year start changes `YEAR()` inside a calculation, or only
  date parts on shelves.

## Revision 2026-10-09: a metric can read its own extract

Found on the DDI Suite, whose sheets read two extracts
(`rpt_tableau__assessment_dashboard` and `rpt_tableau__ddi_dashboard`); one row,
Student Count, has sheets on both.

- A metric may name `datasource:`; it defaults to the checks file's
  `extract.datasource`. Its truth SQL runs against that datasource's extract. A
  row can hold the same Cube measure twice, once per datasource; each is keyed
  `<cube> @ <datasource>` in the results, digest and report.
- The run downloads the workbook once with every extract it needs, applies the
  timing guard to each extract against the Cube fact, and lists each extract's
  refresh time in the snapshots line. The scope guard uses the default
  datasource.
- Extracts of one workbook name the same field differently (DDI: `teacher_name`
  vs `course_teacher_name`). A dimension may give
  `sql_by_datasource: {<datasource>: <sql>}`, and a truth filter may be
  `{sql, datasource}` to apply to one extract only; a plain string still applies
  to every extract.

## Revision 2026-10-09: closed years skip the timing guard

The assessment fact rebuilds five times a day while DDI's extracts refresh
nightly, so a current-year run is only consistent in a narrow morning window. A
window whose academic years have all ended gets no new scores, so the run skips
the timing guard and says so on the snapshots line. DDI and STAT validate on
2025-26; a row that only exists in the current year (DDI's "% Complete (this
week)") waits for a current-year run.

## Revision 2026-10-09: a settle window instead of a tight timing match

Measured on DDI: between a 01:39 extract and the live table 14 hours and three
fact rebuilds later, every changed row was taken within three days of the
refresh (plus a few newly assigned not-taken rows); no older row moved. A checks
file may give `settle: {days, truth, cube}`: the run leaves out scores from that
many days before the extract refreshed, on both sides, with `{cutoff}` filled
in, and skips the timing guard. Cube filters may nest `or` and `and`. A window
of several academic years is compared year by year: `academic_year` joins every
grain.

## Revision 2026-10-09: truth issues go to the domain owner

Found on the DDI Suite. Some gaps are the dashboard's fault, not Cube's: the
Module Dashboard's % Completion formula reads 100% in every module (both counts
look only at rows with a score), and 7 assessments sit in the wrong academic
year in the extract. Those rows should neither fail nor pass on the validator's
say-so. The user cannot rule on each one mid-run, and the domain owner will not
read Asana tasks, so each problem becomes a drafted GitHub issue the user
assigns to the owner.

### Checks file

- A file-level `truth_issues:` map, keyed by slug. Each entry gives `title` (a
  conventional-commit issue title), `what` (plain language), `where`
  (`dashboard`, `rpt` or `source`), `evidence` (aggregates only), and, once
  filed, `issue: <number>` and `ruling: {call, by, on, note}`. `call` is
  `cube-correct` or `cube-wrong`.
- A metric explains gaps through `variants:`, a list of `{explains, sql}` or
  `{explains, num, den}`. `explains` names missing members, truth issues or
  both, so a cell that needs a member and a corrected formula together has one
  variant for the pair. The existing `sql_without` / `num_without` /
  `den_without` fields load as a variant that explains the metric's
  `missing_members`.
- `explains` is authored in the checks file, never computed. The run uses it to
  label cells; the labels are what `latest.json`, the digest, the comment and
  the drafts report. DDI's % Completion, for example:

  ```yaml
  truth_issues:
    completion_always_100:
      title:
        "fix(tableau): DDI Module Dashboard % Completion reads 100% in every
        module"
      where: dashboard
  rows:
    - name: "% Completion (module completion rate)"
      metrics:
        - cube: pct_taken
          num: ... # the dashboard's formula as written
          den: ...
          variants:
            - explains: [completion_always_100]
              num: ... # corrected: students who did not test count
              den: ...
            - explains: [completion_always_100, untagged_assessments]
              num: ... # corrected, tagged assessments only
              den: ...
  ```

- A file-level `open_issues_task: <gid>` names the domain's Open Issues task in
  Asana ("Data Marts + Semantic Layer", one per domain section). Every truth
  issue filed from that file is listed there.

### Verdicts

- A cell that fails against the metric's SQL but matches a variant is explained
  by every name in that variant's `explains`.
- A cell explained by a truth issue ruled `cube-correct` counts as a match. A
  cell explained only by a truth issue ruled `cube-wrong` counts as unexplained.
- Row verdicts, strongest first: `fail`, `incomplete`, `truth_issue` (every gap
  is explained, and at least one by an unruled truth issue), `missing_member`,
  `pass`.
- `latest.json`, the comment and the digest list each truth issue with the cells
  it explains, its issue number if filed, and its ruling if any. A truth issue
  that explains no cell on a run whose issue is closed is reported as stale, so
  its entry can be removed.

### Issue drafts

- Each run writes one draft per unfiled truth issue that explains cells:
  `~/asana-sync/validation/<date>-<dashboard>-issues/<slug>.md`. One problem is
  one draft, however many rows it touches.
- The body follows `.github/ISSUE_TEMPLATE/bug_report.md`: "What's happening"
  states the problem and the discrepancy in numbers; "Steps to reproduce" gives
  the extract query; "Where" names the dashboard, model or source and the Asana
  rows it blocks; the "For Claude" fold-out holds the check SQL, the variant SQL
  and the checks-file path. A label line follows the root CLAUDE.md rule
  (conventional-commit type, source systems, `dbt` when `where` is `rpt`), plus
  a `validation` label and a closing note telling the owner how to answer: label
  `cube-correct` or `cube-wrong`, or fix the source and close the issue.
- Drafts carry aggregates only, with small cells hidden as in comments. No
  student names or ids.

### Filing and rulings (the skill, not the script)

- After the run, Claude lists the drafts. The user picks which to file. For each
  picked draft, Claude creates the issue, creates a `#NNNN | title` subtask
  under `open_issues_task`, writes `issue: <number>` into the checks file, and
  commits it. The user assigns the issue to the domain owner.
- Before each run, Claude reads every filed truth issue's labels and state with
  the GitHub MCP. A `cube-correct` or `cube-wrong` label becomes a `ruling:`
  entry (the labeler, the date, the latest comment's first line as the note),
  committed with the checks file. A ruling already in the file is kept; a label
  that contradicts it is reported, not applied.
- The script never calls GitHub or Asana, so it stays testable offline.

### `sync.py` (user-run, outside the repo)

`truth_issue` gets a new validation tag, `needs-review`, in place of `matched`,
`mismatch` or `unvalidated`. The row is never ticked while it has that tag.
Status still comes from evidence alone: a truth issue neither adds nor removes
`cube-partial`.

### To confirm in the plan

- Whether the `validation`, `cube-correct` and `cube-wrong` labels exist in the
  repo; create them if not.
- Whether `sync.py` creates the `needs-review` tag itself, as it did for
  `untriaged`, or the user creates it once in Asana.
- Whether the GitHub MCP shows who applied a label. If not, `ruling.by` is the
  issue's assignee.

## Revision 2026-10-09: measure each dashboard's settle window

Requested by the user: the settle window's length should come from evidence per
dashboard, not a guess. DDI's 7 days was set before measuring; the measurement
showed every change within 3 days.

- `cube_validate.py settle <checks>` downloads the extracts the checks file
  needs, then compares each one with the live warehouse table behind it. The
  table comes from the datasource caption: `rpt_x (dataset)` reads
  `teamster-332318.dataset.rpt_x`. A caption that does not parse stops the
  command with that message.
- The checks file's `settle:` gains `date:`, the BigQuery SQL for a row's date
  (DDI: `coalesce(date_taken, administered_at)`). The command groups by that
  date and computes every metric on that datasource (its `sql`, or `num` and
  `den`) on both sides, with the file's truth filters and hard filters and the
  window's academic years.
- A day drifts when any value differs. The report lists each drifting day with
  its age in days before the extract refresh and the size of each change. It
  lists rows with no date separately, because no date cutoff can settle them.
- It recommends `days` = the oldest drifting age + 1, at least 1, and prints the
  YAML comment to put beside `settle:` (date measured, live-table age, the
  oldest drift, and the recommendation). Claude writes it into the checks file;
  the user approves the change with the rest of the entries.
- One comparison sees only the changes made between the extract refresh and the
  query. The skill says to run it late in the day, after the fact's later
  rebuilds, and to rerun it when a dashboard's refresh schedule changes.
- BigQuery uses ADC, as before; the command needs no Cube secret.

## Revision 2026-10-09: cube issues prove Cube's formula differs

Requested by the user: a gap can come from Cube's own definition (DDI's %
Complete may count rows where the dashboard counts distinct student-assessment
pairs). Until now that gap only showed as an unexplained `fail`, with the two
formulas side by side for a person to compare. A cube issue turns the suspicion
into evidence and a filed fix.

### Checks file

- A file-level `cube_issues:` map, keyed by slug, beside `truth_issues:`. Each
  entry gives `title` (a conventional-commit issue title), `what`, optional
  `evidence` and `labels`, and, once filed, `issue: <number>` and `closed_on`.
  There is no `where` (it is always the cube) and no `ruling`: the cells the
  variant matches are the evidence.
- A variant's `explains` may name cube issues. Its SQL copies Cube's definition
  over the extract's columns (for DDI, a row count in place of a distinct-pair
  count). A slug is unique across `truth_issues`, `cube_issues` and the metric's
  missing members.

### Verdicts

- A cell that fails as written but matches a variant naming a cube issue is
  explained by that issue: Cube computes something other than what the dashboard
  shows.
- Row verdicts, strongest first: `fail`, `incomplete`, `cube_issue` (every gap
  is explained, at least one by a cube issue), `truth_issue`, `missing_member`,
  `pass`.
- `latest.json`, the comment, the report and the digest list each cube issue
  with the cells it explains and its issue number or draft. A closed cube issue
  that explains no cell is stale, as for truth issues.

### Outputs

- The digest's first section, "Fix in Cube", lists each cube issue with its
  title, what, cells, rows, and the dashboard's and Cube's formulas.
- Each unfiled cube issue that explains cells gets a draft in the run's
  `-issues/` folder. It follows the bug template like a truth-issue draft, with
  `as_written` (the dashboard) and `cube_formula` (the variant) in its query and
  `cube` and `validation` labels. "How to answer" says to fix the cube
  definition and close the issue; the next run checks the fix. If the owner
  thinks the dashboard is the one that is wrong, they say so on the issue and
  the entry becomes a truth issue.
- The skill files a picked cube-issue draft the same way as a truth-issue draft,
  under the checks file's `open_issues_task`.

### `sync.py`

`cube_issue` gets the `mismatch` validation tag: Cube's numbers are wrong, so
the row is never ticked. Status still comes from evidence alone; a cube issue
neither adds nor removes `cube-partial`.

### Related issues (truth issues, cube issues and unexplained gaps)

Requested by the user: before anything is filed, check whether GitHub already
tracks it. In the review step, for each draft and each row under "Investigate",
Claude searches the repo's issues (open and closed) with the GitHub MCP on the
problem's words, the metric, and the models and dashboard involved, and lists
the matches beside it. A match that is the same problem becomes the entry's
`issue:` (no new draft is filed); a related one goes in the new draft's body as
`Related: #N`. The script stays offline: the search is a skill step.

## Revision 2026-10-09: one kind of explained mismatch, with who fixes it

Replaces the truth-issue and cube-issue split above, at the user's request: they
are one mechanism, a formula that explains the gap, and the only decision is who
the fix goes to. Every explained mismatch gets a GitHub issue either way.

- The checks file has one `mismatches:` map, keyed by slug, in place of
  `truth_issues:` and `cube_issues:`. Each entry gives `title`, `what` and
  `fix`: `cube` (the cube builder fixes the Cube definition) or `dashboard` (the
  dashboard maintainer fixes the workbook, its `rpt_` model or the source). A
  `dashboard` entry may give `where`: `tableau` (the default), `rpt` or
  `source`, for the draft's labels and its "Where" line. Optional: `evidence`,
  `labels`, `related`, and once filed `issue` and `closed_on`. `fix` is
  required: when it is unclear, the user decides during review, before anything
  is filed. A file that still uses `truth_issues:` or `cube_issues:` stops with
  a message to rename it.
- A variant's `explains` names mismatches and missing members.
- A cell explained by a `fix: dashboard` mismatch counts as a match: Cube is
  right there, so the row can pass while the dashboard's issue is open. A cell
  explained by a `fix: cube` mismatch is explained, not matched.
- Row verdicts, strongest first: `fail` (a gap nothing explains), `incomplete`,
  `fix_cube` (every gap is explained, at least one by a `fix: cube` mismatch),
  `missing_member`, `pass`. Rulings, the `cube-correct` and `cube-wrong` labels,
  and the `needs-review` tag go away.
- The digest's first sections are "Fix in Cube" and "Fix in the dashboard", each
  listing its mismatches with the cells they explain, both formulas, and the
  draft or issue number. The comment names both lists.
- Every unfiled mismatch that explains cells gets a draft. A `fix: cube` draft
  is labeled `cube` and asks the cube builder to fix the definition; a
  `fix: dashboard` draft is labeled `tableau` (or `dbt` for `rpt`) and asks the
  dashboard maintainer to fix it. Both close when the fix lands and say "if you
  think the other side is wrong, say so in a comment". The related-issue search
  and the filing gate stay as written.
- Before each run, the skill reads each filed issue's state and comments: a
  closed one gets `closed_on`; a comment saying the other side is wrong goes to
  the user, who may flip `fix`.
- `sync.py`: `fix_cube` gets the `mismatch` tag; a `pass` with an open dashboard
  issue gets `matched` like any pass.
