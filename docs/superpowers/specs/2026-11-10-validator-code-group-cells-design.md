# Cube validator: prove code-group cell differences

Issue: #6212. Found by the Attendance Dashboard validation (#6341).

## Intent

The Cube validator proves every difference between a Cube measure and a Tableau
dashboard before it reaches the dashboard's owner. It cannot yet prove one kind:
a row both sides hold, which each side counts differently because the dashboard
counts by a Tableau code group. Example: a day coded `TD` is in both tables. The
dashboard's "# Tardy" counts only its Tardy group (`ET`, `T`, `T10`, `TLE`), so
`TD` counts 0. Cube's `is_tardy` counts every code starting with `T`, so `TD`
counts 1.

No row is missing, so the row reconcile finds nothing to explain. The cells stay
in `investigate`, and because `add-decisions` and `review` refuse a file with
anything in `investigate`, the whole daily attendance file is blocked. That
includes an approved batch of 144 other decisions.

This work lets those cells reach `cause`, and gives the owner a question they
can actually decide.

## Goals

1. A count cell that differs only because of a code rule can be sized and
   proven, row by row, like any other cause.
2. The owner gets 1 question per measure, with enough context to tell a
   definition choice from a data quality problem.
3. An owner who says "the source data is wrong" produces an Asana task for the
   source owner, per the repo's convention, not a GitHub issue.

## Non-goals

- Chronic absenteeism and truancy cells. They are student-level flags at a
  different row grain: #6343.
- Reading code-group codes from the workbook automatically. Codes are written in
  the comparison's `dashboard_columns` (shipped in `b1fb7fe333`). Discovery
  already prints a group's codes (`discover`), so they are copied, not guessed.
- Checking roster measures student by student. See "Roster cells" below.
- Switching the attendance validation files over to the new config. That happens
  on the attendance branch
  (`cristinabaldor/test/claude-attendance-cube-validation`) after this merges.
- Weighted absences (`absent-weighted-roster`). Both sides have the measure
  (absences plus tardies ÷ 3), but Cube has no single per-day column for it, and
  all of its differences are Miami cells where the dashboard is blank. The
  likely cause is missing Miami tardy data (#4927): Cube counts a missing tardy
  as 0 and Tableau's formula goes blank. It is proven on the attendance branch
  as that known-issue cause, not by this mechanism. The analyst agreed.
- ISS days (`iss-roster`). Both sides use the same codes (`S`, `ISS`); every
  difference is a Miami cell where Cube is blank, the same #4927 cause, proven
  on the attendance branch.

## Anti-goals

- No student value reaches GitHub. Every rule that holds today (masking counts
  under 10, refusing a literal compared with an identifying column) holds for
  the new question and its usage profile.
- No free SQL in the validation YAML beyond what `dashboard_columns` already
  allows. `RowSpec.values` stays a list of plain column pairs.
- No cell reaches `cause` on a guess. A row the proof does not name still falls
  to `UNEXPLAINED`.

## Decisions made with the analyst

### How a code-group cell gets proven

- The comparison declares the dashboard's code group as a structured list (the
  dashboard column and its codes, copied from `discover`'s output), and the
  validator builds the computed dashboard column from it, the way
  `dashboard_columns` does today (for example the Tardy group: `att_code` in
  `ET`, `T`, `T10`, `TLE`, as 0/1). The comparison pairs it with Cube's column
  in `rows.values` (`{dashboard: tardy_group, cube: is_tardy}`). _My call:_ a
  list, not a SQL expression, so the same codes can be applied to Cube's
  `attendance_code` for the usage profile.
- A row both sides hold, whose values differ, is a `value_differs` row, as now.
- **New: a sum mode for cell sizing.** Once a comparison pairs `rows.values`,
  cells are sized by `_rebuilt`, which rebuilds each side as the mean of the
  value column. The roster measures are sums, so the comparison declares that
  its measure adds up, and `_rebuilt` then rebuilds each side's cell as the sum
  of its value column. The per-bucket Cube and dashboard sums the run keeps per
  cell are expected to be enough. _My call._ (Changing `_SIGN` alone, as the
  first draft said, would change nothing: `_SIGN` serves only comparisons with
  no `rows.values`.)
- The proof names each disagreeing row's cause by its code (for example, "TD
  counts in Cube, not on the dashboard"). Every row must be named, as now.
- **Missing source data is a cause, not a code disagreement.** Miami's Focus
  rows carry no tardy or suspension flags (#4927), so Cube is blank where the
  dashboard shows 0 (# ISS, # OSS, # Tardy in the Miami cut). Those cells are
  proven as a known-issue cause pointing at #4927. _My call._

### Roster cells

- The 5 roster measures (# Tardy, # Days Absent, # ISS, # OSS, weighted
  absences) are compared by grade and region, not by student. The analyst's
  reasoning: a difference at that level leads to the individual students through
  the row-level work, which stays at 1 row per student per day.
- Individual students stay visible only where they are today: the analyst's
  terminal and the local `triage.json`.

### The owner's question

- 1 question per measure: # Tardy, # Days Absent, # OSS, % On-Time.
- **The owner gives a call per disagreeing code inside that question** (for
  example `TD` `deliberate`, `TE` `fix_source`). The analyst decided this, so
  the answers JSON and `record-answers` take 1 call per code, and each code's
  call records onto the decisions for that code's cause. A code shared by 2
  comparisons (tardy and on-time) gets 1 call, recorded on both.
- It states each side's rule in plain words (from the comparison's
  `definitions:`), then lists every code where the 2 rules disagree.
- The disagreeing codes come from running both rules over every code in Cube's
  daily fact, across every year, not only the codes seen in the validated year.
  _My call._
- For each disagreeing code, a usage profile, because a disagreeing code may be
  a data quality flag rather than a definition choice:
  - days per academic year, across every year in Cube's daily fact, so a code
    that stopped or started being used shows
  - where it is used: number of schools, and which regions
  - its share of all coded days that year
- Counts under 10 show as `<10`, as everywhere else on GitHub. Schools are
  listed by name (a school is not a person), and a school's count under 10 is
  masked. _My call._
- The profile comes from 1 aggregate BigQuery query on
  `fct_student_attendance_enrollment_daily` (code by academic year and school).
  `triage` runs it, priced and capped like its other queries, and caches it in
  `triage.json`, so `review` stays offline. The same query goes in the
  question's Reproduce block so the owner can re-run it on today's data. _My
  call_ (the first draft had `review` run it, which would make `review` need
  credentials).
- Answers: `fix_cube`, `fix_dashboard`, `deliberate`, or `fix_source`.

### `fix_source` goes to Asana

- In the owner's session (`cube-validation-answers`), a `fix_source` answer
  drafts an Asana task for the source owner instead of a GitHub issue. The draft
  carries the code's usage profile. The owner approves it, the session creates
  it, and its link becomes the decision's `task`.
- **Where it goes (the analyst decided):** a subtask of the dashboard's Asana
  task in the Data Marts + Semantic Layer project (for attendance, the
  "Attendance Dashboard" task), assigned to whoever the owner names. The
  validation file needs that parent task's link; _my call:_ a third `tasks:`
  key, `dashboard`, beside `cube_fix` and `dashboard_fix`.
- The validator's loader already accepts an `https://` link as a task.
- Both skills change, not only the owner's: the analyst's own `fix_source`
  (`cube-validation` steps 8 and 9) also becomes an Asana subtask, in line with
  the `pr-ci-review` convention that source-data fixes are Asana tasks owned by
  the source owner. _My call._

## Constraints

- Validator code: `scripts/cube_validation/`. Run it through the pytest runner
  described in the `cube-validation` skill; its unit tests are under
  `tests/scripts/cube_validation/`.
- Relevant code today:
  - `compare.py`: buckets each reconciled row (`value_differs` when values
    differ on a row both sides hold).
  - `confirm.py`: `_SIGN`, `_sizable`, `_rebuilt`, `link_cells` size and link
    cells; the proof checks (`_identifies`, `_leaves`) guard privacy.
  - `config.py`: `RowSpec`, `dashboard_columns`.
  - `report.py`: `_questions`, `render_review_issue`, the Reproduce block.
  - `answers.py`: `fix_source` requires a task.
- The `cube-validation` and `cube-validation-answers` skills document the
  runbook; both change with this work.
- Tableau writes stay in `TEMP-CB`. The tool still posts nothing itself.

## Left to the builder

- How a comparison declares sum mode (a config key, or reading the measure's
  type from `members.json`), and confirming the run's per-bucket sums suffice
  for it.
- The shape of the structured code-group list in the YAML.
- How a roster comparison is expressed at grade and region grain. The analyst's
  suggestion: drop the student from `dims` and let `split_rows: sum` add each
  grade's rows from the existing export. Fall back to `shelves:` if that does
  not hold.
- Whether a rate cell (% On-Time) needs its own sizing rule beyond the count
  rule, given that `_rebuilt` already rebuilds a rate from 1 value column.
- The exact layout of the usage profile in the issue body, within GitHub's body
  cap (`review` already moves long blocks into comments).

## Done when

- The attendance daily view's 4 code-group cell sets (`tardy-roster`,
  `absences-roster`, `oss-roster`, `ontime-grade-rollup`) reach `cause` through
  `triage confirm --cells`, once the attendance branch switches to the new
  config. (`iss-roster` and `absent-weighted-roster` reach `cause` through the
  #4927 cause on that branch.)
- A sum-mode comparison sizes its cells as sums, and an existing mean-mode
  comparison (ADA, % On-Time) sizes exactly as before.
- `review` renders 1 question per measure with each side's rule, the disagreeing
  codes and their usage profiles, all masked.
- An owner's `fix_source` answer produces an approved Asana task whose link is
  the decision's `task`.
