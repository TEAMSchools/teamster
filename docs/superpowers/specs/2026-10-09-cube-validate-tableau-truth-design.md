# Cube validation against what Tableau shows: design

Status: sections approved in conversation 2026-10-09; awaiting review of the
written spec. Refs #5856.

## Goal

Check that Cube returns the numbers a Tableau dashboard actually shows a person,
in every state a person can reach that matters, and turn each explained gap into
a GitHub issue for whoever fixes it.

- **Users:** data-team analysts working in Claude Code. Claude runs the steps;
  the analyst approves the states, the mappings and every issue before it is
  filed.
- **Success:** someone without this design's history can validate a new
  dashboard, and the tool never blames Cube for an error in its own SQL.
- **In scope:** validation only.
- **Out of scope:** build mode (its own issue, after this ships), the weekly
  scheduled run (#5842), moving `~/asana-sync/sync.py` into the repo.

Model case: #5692. `student_assessment_scores_view` dropped about 1 in 10 state
test scores; STAT in Tableau was right and Cube was short.

## Decisions

- **Truth is Tableau's own export.** A review copy of the workbook is published
  to the analyst's non-production project, every sheet a person sees is exposed
  as its own view, and each sheet is exported with `tableauserverclient`
  `populate_csv`. The tool does no math on the Tableau side: the export already
  carries every filter, calculation, parameter and click.
- **Only reachable states.** The default view, filter and parameter values set
  with `CSVRequestOptions().vf(name, value)`, and clicks reproduced as filters
  on the click's fields. Grains come from what Tableau returns, never from the
  `.twb` shelves.
- **Causes come from the extract.** On cells where Cube differs, SQL over the
  downloaded `.hyper` extract explains why. That SQL is trusted only after it
  reproduces Tableau's displayed values, so the tool can tell its own error from
  Cube's.
- **Compared at the precision shown.** A displayed 36.24 matches Cube's 36.2381.
- **Every explained gap becomes an issue draft.** Nothing is filed until the
  analyst has seen the full list and the related-issue search.

## Spike evidence (2026-10-09, DDI Suite, Module Dashboard)

- A dashboard's own export returns only its first sheet (0 rows on the Module
  Dashboard; the crosstab endpoint refused). Hence the review copy.
- Exposing a sheet means removing `hidden='true'` from its
  `<window class='worksheet'>`. Network Overview then exported 117 rows with
  totals ("All") and multi-value marks ("\*"); `vf("Grade Level", "5")` cut it
  to 20.
- Tooltip fields come with the export: Assessments Over Time exported "Avg. %
  Completion" alongside its marks.
- Drill-down sheets exported empty until 2 edits on the copy: dashboard actions'
  `on-empty` from `none` to `all`, and stripping the sheets' saved
  `[Action (...)]` filters and slice entries. Then `vf("Title", ...)` reproduced
  a click.
- A `vf` on a wrong field name is silently ignored. Values come both formatted
  ("100%") and raw ("1"). `vf` field names are the captions shown in the sheet.
- Filter fields nest measurably. On the DDI weekly extract (2026-27 rows),
  Goodman-Kruskal lambda: `school` inside `region` 1.00, `school` inside
  `head_of_school` 1.00, `homeroom_section` inside `grade_level` 0.996,
  `homeroom_section` inside `school` 0.91 (homeroom names repeat across
  schools), `week_start_monday` inside `term` 1.00, `module_code` inside
  `module_type` 1.00. `grade_level` is not inside `school`.

## Section 1: components

### Files

- `scripts/cube_validate_snapshot.py`: the Tableau side. No Cube calls.
  - `plan <workbook>`: reads the `.twb` (dashboard filter cards, parameter
    controls, actions) and the extract (distinct values, counts, nesting scores)
    and writes a proposed `trees:` and `states:` for Claude to show the analyst.
  - `open <checks>`: sweeps stale review copies, publishes a fresh one, exports
    the must states and the top level of each tree, downloads the extracts.
  - `export <checks> --states <ids>`: exports more states into the open session.
  - `close <checks>`: deletes the review copy and confirms it is gone.
- `scripts/cube_validate.py`: the Cube side. Reads a snapshot, never calls
  Tableau.
  - `compare <checks>`: diffs each export against Cube and proposes the next
    descent level's states.
  - `explain <checks>`: runs the trust gate, then the variant engine.
  - `drafts <checks>`: writes the digest, one issue draft per unfiled mismatch,
    and `latest.json`.
  - `settle <checks>`: measures the settle window (ported from v1).
- `.claude/skills/cube-dashboard/SKILL.md`: the runbook. Claude steps through
  plan, analyst edits, open, the compare/export loop, close, explain, drafts,
  and the filing review.
- `.claude/skills/cube-dashboard/checks/<dashboard>.yml`: one per dashboard
  (Section 2).
- Both scripts are standalone PEP 723 scripts, per `scripts/CLAUDE.md`. Each is
  added to its script catalog.

### Where data lives

- Snapshots: `~/.cache/cube-validate/<workbook>/<date>/`. Outside the repo,
  because they hold student-level rows.
- Retention: the latest 2 snapshots per workbook (enough for the run-twice check
  and follow-up reruns). `open` deletes older ones first.
- Reports and drafts: `~/asana-sync/validation/`, as in v1.

### Credentials

Both scripts need secrets (the Tableau PAT and `CUBE_API_SECRET`), so each runs
inside a throwaway pytest under `tests/`, per the root CLAUDE.md. The skill
writes and deletes that wrapper; the analyst never handles it.

## Section 2: the checks file

One per dashboard. Grains and values are not in it; they come from Tableau.

```yaml
workbook: DDI Suite
workbook_luid: <luid>
review_project_luid: ddc817c2-6bc7-4bca-8be9-e385f95b9ebc # TEMP-CB
settle: { days: 5, date: "coalesce(date_taken, administered_at)" }

# Asana measure rows, so sync.py can tag them. A row's verdict is the worst
# verdict across every cell of its measures.
rows:
  "<asana row gid>": [kipp_ddi.pct_complete]

# Derived by `plan`, edited by the analyst. Each tree is a list of levels.
trees:
  who: [region, head_of_school, school, grade_level, course_section]
  when: [term, week_start_monday]
  what: [module_type, module_code]
cross_cuts: [iep_status, ml_status, status_504, state_test_proficiency]

# Proposed by `plan`, edited by the analyst. Descent states are generated
# during the session and recorded in the manifest, not here.
states:
  - id: module-dashboard--default
    dashboard: Module Dashboard
  - id: module-dashboard--group-by-teacher
    dashboard: Module Dashboard
    params: { Group By: Teacher }
  - id: module-dashboard--click-sections-details
    dashboard: Module Dashboard
    click: { action: Sections > Details, mark: largest }

# Tableau caption -> Cube member and extract SQL, per sheet.
sheets:
  Network Overview:
    datasource: rpt_tableau__assessment_dashboard
    dims:
      School: { cube: kipp_ddi.school_name, sql: school }
      Grade Level: { cube: kipp_ddi.grade_level, sql: grade_level }
    measures:
      Avg. Percent Correct:
        cube: kipp_ddi.avg_percent_correct
        sql: avg(percent_correct)
      Avg. % Completion:
        cube: kipp_ddi.pct_complete
        num: count(distinct if(is_complete, student_number, null))
        den: count(distinct student_number)
        variants: # Section 6
          - explains: [dup_not_tested_rows]
            cube_filters:
              [
                {
                  member: kipp_ddi.is_duplicate_row,
                  operator: equals,
                  values: ["false"],
                },
              ]

mismatches: {} # Section 6
```

- Member and column names above are illustrative; the plan confirms the real
  ones.
- A measure that is a table calculation (percent of total, running sum) says
  `table_calc: <kind>`. `compare` rebuilds it from Cube's full result for that
  state instead of comparing cell by cell.
- Per-extract SQL (`sql_by_datasource`) and per-extract Cube filters
  (`datasource:` on a filter) carry over from v1.

## Section 3: which states get visited

### Where the choices come from

- Filters and parameters: the filter cards and parameter controls placed on each
  dashboard in the `.twb`. This reads what a person can click, not grains.
- Values: distinct values from the extract, with their student counts. Blank
  counts as a value.
- Clicks: the dashboard actions in the `.twb`; mark values come from the source
  sheet's own export.

### Must (always visited)

- The default view of every dashboard.
- Every value of each parameter that changes what is shown ("Group By",
  "Dashboard View", "Display Metric").
- Every value of each filter built on a calculated field.
- Every filter whose saved default is not "All", at its default and at "All".
- The descent down each tree (below).
- Every value of each cross-cut, at the top level.
- Academic year: the current and the prior year.
- The blank/"Null" value of any filter that has one.
- One click per filter action: the largest mark and one small mark (at least 10
  students).

### Optional (off until the analyst turns it on)

- Any plain dimension filter not in a tree, one filter at a time: the largest
  value, the smallest with at least 10 students, and blank if present.
- Named combinations across trees (for example `school × module_code`).

### Skipped, with the reason shown

- Filters on person names (`lastfirst`, `student_name`, teacher names outside a
  tree): person-level.
- Hyperlink and URL actions: they open another page.

### Trees: derived per dashboard

- `plan` scores every pair of the dashboard's filter fields on its own extract
  with Goodman-Kruskal lambda (how well the finer field predicts the coarser
  one, corrected for lopsided fields). 0.90 or higher is nested; 0.85 to 0.90 is
  shown to the analyst to decide; lower is not nested.
- Nested pairs form trees (who, when, what). Fields inside no tree are
  cross-cuts. A field with one value plus blanks is a yes/blank cross-cut.
- A level whose field is not inside its parent across the whole extract (grade
  inside school) is applied within the parent: the state filters both.
- The analyst's edited trees are saved in the checks file. Each later `plan` run
  re-scores them and warns if a level has drifted below 0.90.

### The descent

1. `open` exports each tree's top level (one state per value, or one state if
   the sheet already breaks out by that field).
2. `compare` diffs that level and names the next level's states: every child
   that mismatches, plus the largest and the smallest matching child (at least
   10 students).
3. `export` exports those states. Steps 2 and 3 repeat.
4. The descent stops at a slice under 10 students or at the tree's last level.
5. At the level where a gap is narrowed down, each cross-cut is split again, to
   test whether the gap is specific to it.

Matching children are sampled because rounding hides small gaps at the top,
errors can cancel between siblings, and a bad filter can bite at one school
only.

## Section 4: the session

1. **Sweep.** `open` deletes any `ZZ-REVIEW` workbook in the review project
   older than 24 hours.
2. **Publish.** The review copy is the live workbook with every dashboard sheet
   exposed, actions' `on-empty` set to `all`, and saved click filters stripped.
   Named `ZZ-REVIEW <date> <workbook>`. Every publish passes the
   `tableau-workbook-xml` skill's gates.
3. **Export.** One CSV per sheet per state:
   `<snapshot>/csv/<sheet-slug>/<state-id>.csv`.
4. **Download** each extract the workbook uses: `<snapshot>/extract/*.hyper`.
5. **Close.** Delete the copy, then list the project to confirm it is gone. The
   pytest wrapper calls `close` in a finalizer, so a failed step still closes.

### State ids

Stable slugs from the dashboard, then the sorted filters, parameters and click:
`module-dashboard--region-newark--school-<slug>`. Reruns line up by id.

### Manifest

`<snapshot>/manifest.json` records the workbook revision, each extract's refresh
time, the copy's LUID, and per state: its filters, the row count of each sheet,
and the filter-took-effect result.

## Section 5: compare

- **Cube query:** one per sheet per state, at that export's grain (its dimension
  columns), with the state's filters translated through the sheet's `dims`, the
  per-extract Cube filters, and the settle window. Not one query per row.
- **Values:** each measure cell against Cube at the precision the export shows.
  Formatted ("100%") and raw ("1") values both parse.
- **Row sets:** a slice Tableau shows that Cube lacks, and the reverse, is a
  mismatch. This catches a filter that hides whole slices.
- **Numerator and denominator:** every rate whose counts appear in the export
  (usually as tooltip fields) has each count compared too. This catches a rate
  whose two counts share the same wrong filter (DDI's % Completion).
- **Totals:** "All" rows compare against Cube without that dimension. This
  catches an average of averages compared with a true ratio.
- **Not comparable:** "\*" marks, table calcs with no `table_calc:` mapping,
  values that do not parse. Counted in coverage, never passed.
- **Scope guard** (from v1): before comparing, one student count per region. A 0
  means the viewer's Cube scope is narrower than the dashboard's; the run stops.
- **Pre-aggregation check** (from v1): on a mismatched cell, Cube `/sql` records
  whether the query hit a rollup, since a stale rollup is a different fix.
- Output: `<snapshot>/cells.parquet`, one row per cell with status `match`,
  `mismatch` or `not_comparable`.

## Section 6: explain, mismatches and verdicts

### The trust gate

- Extract SQL for a measure must reproduce Tableau's values on the default view
  before it may explain anything. If it fails, every cell of that measure is
  `incomplete` with the reason "extract SQL does not reproduce Tableau".
- On each mismatched cell, the measure's SQL must also reproduce that cell's
  Tableau value. If it does not, the cell stays unexplained.

### Variants (from v1)

- Dashboard-side: `sql`, or `num`/`den`, or `where:` (limits every aggregate of
  the measure's own formula).
- Cube-side: `cube_filters:`, an extra Cube query meaning "Cube without these
  rows".
- Each variant names the mismatches it `explains`. A cell is explained only when
  one variant accounts for its whole gap; if one cause in the cell is not wired,
  the cell stays unexplained.

### Mismatches (from v1)

`mismatches:` is keyed by slug. Each entry gives `title` (a conventional-commit
issue title), `what` (plain language), and `fix`:

- `cube`: the cube builder fixes the Cube definition.
- `dashboard`: the dashboard maintainer fixes it. Optional `where: rpt` when the
  fix is in the `rpt_` model.
- `source`: the source owner fixes the data.
- `undecided`: the domain owner decides, answering with the label `fix-cube` or
  `fix-dashboard` or a comment starting with the word. Their issue becomes the
  fix ticket.

Optional: `evidence` (aggregates only), `labels`, `related` (issue numbers), and
once filed `issue` and `closed_on`.

### Verdicts

Per cell, then per Asana row (the worst of its cells), strongest first:

`fail` > `incomplete` > `fix_cube` > `fix_source` > `undecided` >
`missing_member` > `pass`

- `fix:` is what the checks file says about a mismatch; the verdict is what the
  tool outputs. They map as below. A `fix: dashboard` explanation gives `pass`,
  because Cube is right.

| Cause                    | Verdict          |
| ------------------------ | ---------------- |
| none, gap unexplained    | `fail`           |
| trust gate failed        | `incomplete`     |
| `cube`                   | `fix_cube`       |
| `source`                 | `fix_source`     |
| `undecided`              | `undecided`      |
| member missing from Cube | `missing_member` |
| `dashboard`, or no gap   | `pass`           |

## Section 7: outputs, issues and privacy

### Outputs

- **Coverage report**, every run: states visited, states skipped with the
  reason, `filter_ignored` and `export_failed` states, not-comparable cells by
  cause.
- **Digest** (from v1): "Fix in Cube", "Fix in the dashboard", "Fix in the
  source" and "Owner to decide", each mismatch with its cells, both formulas and
  its draft or issue number; then unexplained gaps under "Investigate".
- **Issue drafts** (from v1): one per unfiled mismatch that explains cells, in
  `~/asana-sync/validation/<date>-<dashboard>-issues/<slug>.md`. Bug template, a
  runnable query, examples coarsest first, labels per the root CLAUDE.md plus
  `validation`.
- **`latest.json`** for `sync.py`: one entry per Asana row with its verdict.
  `pass` is tagged matched; `fail`, `fix_cube`, `fix_source`, `undecided` and
  `missing_member` are tagged mismatch; `incomplete` or never run is
  unvalidated. A row is ticked only when it is cube-covered and matched.

### Filing (the skill, not the script)

1. Claude searches the repo's issues (open and closed) for each draft and each
   unexplained gap, and lists the matches beside it.
2. The analyst sees the full list of drafts and matches before anything is
   filed, and picks which to file.
3. Claude files the picked drafts, writes `issue:` into the checks file, and
   commits it.

A follow-up mode ("follow up on <dashboard>") reads every filed issue's state,
labels and comments, updates the entries (`closed_on`, `fix` on an undecided
answer), and reruns only the states those cells came from. The scripts never
call GitHub or Asana, so they stay testable offline.

### Privacy (from v1)

- A dimension marked `person: true` shows as "a student"; `person: <label>`
  shows that label ("a teacher").
- Cells under 10 students show as "small cell" in every output.
- Workbook filters that exclude test records are marked private and never reach
  a draft.
- Snapshots never enter the repo. Drafts and reports carry aggregates only.

### Settle window (from v1)

Both sides leave out rows dated within `settle.days` before the extract's
refresh. `settle` measures the right number from the live `rpt_` table. DDI
measured 4 days on the weekly extract and 3 on the assessment extract; 5 is
recommended.

## Section 8: error handling

When the tool cannot tell whose fault a gap is, the cell is `incomplete` and
nobody is blamed.

| Case                                        | Result                                                                                                                 |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Publish fails a `tableau-workbook-xml` gate | Stop before anything is on the server                                                                                  |
| A filter is silently ignored                | State `filter_ignored`, not compared. Rows equal to the parent count as ignored unless the extract says they should be |
| An export times out or hits a 429           | Back off, retry 3 times, then `export_failed`                                                                          |
| The extract refreshes mid-session           | Each export re-checks the datasource's `updatedAt`; a change ends the session                                          |
| `close` fails                               | Loud error with the copy's LUID and URL; the next `open` sweeps it                                                     |
| Cube 429 or 5xx                             | Continue-wait polling and back-off (from v1)                                                                           |
| A mapped member is not in `/v1/meta`        | `missing_member`                                                                                                       |
| Trust gate fails on the default view        | Every cell of that measure `incomplete`                                                                                |
| Trust gate fails on one cell                | That cell unexplained                                                                                                  |
| A value does not parse                      | Not comparable, counted in coverage                                                                                    |
| A slice under 10 students                   | Descent stops; compared internally, shown as "small cell"                                                              |

## Section 9: testing

### Offline unit tests (committed, no credentials, no student data)

- `tests/scripts/test_cube_validate_snapshot.py` and
  `tests/scripts/test_cube_validate.py`, loading each script with `importlib`
  per `scripts/CLAUDE.md`.
- Synthetic fixtures: a small `.twb` with filter cards, parameters and actions;
  a small `.hyper` built in the test; CSV exports with "100%", "1", "All" and
  "\*".
- Ported code brings its v1 tests: Cube client, Hyper reader, sqlglot
  translation, variant engine, digest and drafts, `settle_drift`, person
  masking.
- New tests: nesting scores (blank as a value, lopsided fields), state ranking
  and stable ids, `filter_ignored` detection, value parsing at the shown
  precision, the row-set, numerator/denominator and totals diffs, descent child
  selection, retention purge, the stale-copy sweep.
- `tableauserverclient` calls are mocked, and each mocked call is exercised on
  its runtime path.

### Offline acceptance: synthetic replay of the DDI gap types

| Gap type                          | `fix:`      | Verdict      |
| --------------------------------- | ----------- | ------------ |
| Duplicate rows in Cube's fact     | `cube`      | `fix_cube`   |
| Both counts read only scored rows | `dashboard` | `pass`       |
| Cube leaves out untagged rows     | `undecided` | `undecided`  |
| The extract leaves out rows       | none        | `incomplete` |

Plus a planted bad mapping, which must come back `incomplete`, never `fix_cube`.

### Live acceptance (once, before the PR; results redacted into the PR body)

1. A full DDI Suite session re-finds the 4 known DDI gaps and the #3801 year-tag
   assessments.
2. 2 snapshots of the same extract export identically.
3. After `close`, the review project holds no `ZZ-REVIEW` copy.

## Carried over from v1, and left behind

Copied deliberately with their tests from `scripts/cube_validate.py` on
`cristinabaldor/feat/claude-cube-validate-skill`: the Cube REST client (JWT,
Continue-wait polling, 429/5xx back-off, per-thread clients), the Hyper reader
and sqlglot translation, the variant engine (`explain`, `summarize`,
`_filtered`), the digest and issue-draft writers, `settle_drift`, person
masking.

Left behind: grain proposal from the `.twb`, the Tableau-construct audit, the
old checks files.

## To confirm in the plan

- Which `vf` caption each tree level uses per dashboard (homeroom is `team` or
  `course_section` on the Module Dashboard).
- Whether `vf` accepts several values for one field, for the "All" versus
  default checks.
- Whether the datasource's `updatedAt` or the workbook's is the right
  mid-session refresh check.
- Whether `tableauhyperapi` installs cleanly as a PEP 723 dependency in the
  Codespace (it did with `uv run --with` during the spike).
