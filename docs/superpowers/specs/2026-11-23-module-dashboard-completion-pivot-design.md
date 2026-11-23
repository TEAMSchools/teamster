# Module Dashboard: accurate completion % and a course-subject pivot

Issue: [#6474](https://github.com/TEAMSchools/teamster/issues/6474)

## Goal

Two changes to the Module Dashboard in the DDI Suite workbook:

1. "% Completion" is accurate, can be shown, and its "at least 75%" filter hides
   the cells it should.
2. The 2 main heatmaps can put either grade level or high school course subject
   across the top.

Both are built on the review copy `ZZ-REVIEW 2026-11-12 DDI Suite goal columns`
and delivered as a new review copy. Production is out of scope.

## Decisions already made

| Decision                 | Choice                                                       |
| ------------------------ | ------------------------------------------------------------ |
| Base workbook            | Review copy, luid `652f1c0a-371a-42ee-807a-61a3915e3af2`     |
| Completion denominator   | Assessments whose `administered_at` is today or earlier      |
| Course subject field     | The assessment's `subject_area`                              |
| Miami completion         | Reads about 100% this year; accepted                         |
| Workbook tooling         | The `tableau-workbook-xml` skill, for every edit and publish |
| Where the change is made | The workbook only. No dbt change (see _Why no dbt change_)   |

## What is wrong today

"% Completion" reads 100% in every cell, so the saved filter (`% Completion` at
least 0.75) hides nothing.

The extract `rpt_tableau__assessment_dashboard` holds one row for each
assessment a student was assigned and has not taken. That row has a null
`response_type`, a null `date_taken` and a null `percent_correct`. A taken
assessment has an `overall` row instead.

Two things in the workbook drop the not-taken rows before completion is
computed:

- Every Module Dashboard sheet filters `response_type` to `O` and `overall`, and
  that filter is a context filter. Tableau applies context filters before it
  evaluates a `FIXED` expression, so the completion calcs never see a not-taken
  row.
- The denominator calc counts only rows where `response_type = 'overall'`.

The denominator is therefore the students who took the assessment, and the ratio
is 1.

The Asana subtask this replaces suspected a different cause: the numerator is
fixed on `is_pathways` and the outer expression on `is_replacement`. That
mismatch is real and this design removes it, but it is not what produces 100%.

### What the numbers should look like

Measured on prod `rpt_tableau__assessment_dashboard`, school year 2026-27,
tagged assessments, one row per student and assessment:

| Region   | Date passed, taken / assigned | Last 14 days only | Not yet given |
| -------- | ----------------------------- | ----------------- | ------------- |
| Camden   | 69%                           | 49%               | under 1%      |
| Newark   | 73%                           | 53%               | under 1%      |
| Paterson | 75%                           | 56%               | 0%            |
| Miami    | 100%                          | 100%              | none          |

Miami has no not-taken rows: Focus Apex data holds a row only for a student who
tested.

Who counts as assigned is already right. `int_assessments__scaffold` expects a
student only if they were enrolled in the course on the administered date.

## Design: completion

### Definitions

- Assignment: one student and one assessment. In the extract it is the `overall`
  row when taken and the null-`response_type` row when not.
- Counted: an assignment whose `administered_at` is today or earlier.
- Taken: a counted assignment with an `overall` row whose `percent_correct` is
  not null.
- Cell: `academic_year`, `schoolid`, `subject_area`, `module_type`,
  `module_number`, `is_replacement`, and the heatmap column (see _Design:
  pivot_). `is_pathways` leaves the grain.
- Cell completion: taken assignments over counted assignments in the cell.

An assessment that is not yet due has no counted assignments, so its cell
completion is null and the 75% filter hides it, including any early scores.

Replacement sittings exist only when taken (the scaffold has no not-taken
off-grade row), so a replacement cell reads 100%. `is_replacement` stays in the
grain to keep those rows out of the on-grade cell.

### Calculation changes

All three calcs keep their internal names, so every sheet that already uses them
keeps working.

| Calc (caption)                  | Internal name                      | New formula                                |
| ------------------------------- | ---------------------------------- | ------------------------------------------ |
| `# Students Possible - Overall` | `[Student Baseline Count (copy)]`  | `FIXED` cell: distinct counted assignments |
| `# Students Complete - Overall` | `[Calculation_860187586860363778]` | `FIXED` cell: distinct taken assignments   |
| `% Completion`                  | `[% Completion (copy)]`            | Complete divided by Possible, no `SUM`     |

An assignment is counted distinctly as
`STR([student_number]) + '|' + STR([assessment_id])`, because about 0.7% of
extract keys repeat.

Exact formulas:

```text
# Students Possible - Overall
{FIXED [academic_year], [schoolid], [subject_area], [module_type],
       [module_number], [is_replacement], [Heatmap Column]:
    COUNTD(IF (ISNULL([response_type]) OR [response_type] = 'overall')
              AND [administered_at] <= TODAY()
           THEN STR([student_number]) + '|' + STR([assessment_id]) END)}

# Students Complete - Overall
{FIXED [academic_year], [schoolid], [subject_area], [module_type],
       [module_number], [is_replacement], [Heatmap Column]:
    COUNTD(IF [response_type] = 'overall' AND NOT ISNULL([percent_correct])
              AND [administered_at] <= TODAY()
           THEN STR([student_number]) + '|' + STR([assessment_id]) END)}

% Completion
[# Students Complete - Overall] / [# Students Possible - Overall]
```

`[Heatmap Column]` is added by the pivot work. Until it exists, the grain uses
`[grade_level]` in its place.

### Filter change

The `response_type` filter stops being a context filter and becomes an ordinary
filter, on these 17 sheets:

- The 15 sheets that share it as filter group 27: 9 Module sheets and 6
  Assessment Dashboard sheets. A shared filter is changed as a whole.
- `Module - Overall - Band Distribution` and
  `Module - Overall - Student Distribution`, which carry their own copy.

Its members (`O`, `overall`) do not change, so every sheet shows exactly the
rows it shows today. Only `FIXED` expressions see more rows. The only `FIXED`
calcs reachable from those sheets are the 3 completion calcs and 2 performance
band calcs that already name `response_type` in their own formula, so no other
number moves.

The 4 Module sheets with no completion filter (`Module - Standard - *`,
`Module - RGs - *`) are not touched.

### Showing completion

Today 2 places show `AVG(% Completion)`: the measure row of
`Module - Overall - Summary` and the tooltip of
`Module - Overall - Assessments Over Time`. When a mark covers several cells,
that is an average of cell rates weighted by the number of takers. The owner's
call on #6415 is that completion is pooled: taken over assigned.

A new calc replaces `AVG(% Completion)` in those 2 places:

```text
% Completion (Pooled)
SUM({INCLUDE [academic_year], [schoolid], [subject_area], [module_type],
             [module_number], [is_replacement], [Heatmap Column]:
        MIN([# Students Complete - Overall])})
/
SUM({INCLUDE [academic_year], [schoolid], [subject_area], [module_type],
             [module_number], [is_replacement], [Heatmap Column]:
        MIN([# Students Possible - Overall])})
```

It takes each cell's counts once and sums them across the cells in the mark.
Default format `p0%`.

No new tooltip line or mark label is added. The swap reuses the existing tooltip
run and changes only the field it points to, which is the one tooltip edit the
skill treats as safe.

### Known limits of the completion number

- A cell where nobody has a score has no row on the sheet, so it shows no mark
  and is not in a pooled number. Completion is overstated for a mark that covers
  such a cell.
- Cell completion covers every assigned student in the cell. It does not change
  with the student-group filters (IEP, bucket, tutoring). The filter's job is to
  hide a cell that is not mostly complete, whatever group is on screen.
- The pooled number covers only the cells the 75% filter lets through. To see
  completion for every cell, a user lowers the slider.
- Miami reads about 100%.
- Completion on the Assessment Dashboard's summary sheet also becomes accurate
  for tagged assessments, since it uses the same calcs. Untagged assessments
  have no not-taken rows and keep reading 100%.

## Design: pivot

### Control

A new string parameter, caption `Heatmap Columns`, with 2 values: `Grade Level`
(default) and `Course Subject`. Its control sits beside the existing
`Dashboard View` control on the Module Dashboard.

### Fields

Two new calcs on the `rpt_tableau__assessment_dashboard` datasource:

```text
Heatmap Column  (string dimension)
IF [Parameters].[Heatmap Columns] = 'Course Subject' AND [grade_level] >= 9
THEN [subject_area]
ELSEIF [grade_level] = 0 THEN 'K'
ELSE STR([grade_level])
END

Heatmap Column Sort  (integer dimension)
IF [Parameters].[Heatmap Columns] = 'Course Subject' AND [grade_level] >= 9
THEN 100
ELSE [grade_level]
END
```

`Course Subject` changes only grades 9 to 12. A K-8 row keeps its grade level in
either mode, so a view that mixes school levels still reads sensibly. The rule
uses `grade_level`, not the workbook's `School Level (School)` group, because
that group is a hard-coded school list that leaves out Paterson (#5326).

`K` matches the alias the grade-level header shows today.

### Sheets

On `Module - Overall - Network Overview` and
`Module - Overall - Assessments Over Time`, `Heatmap Column` replaces
`grade_level` on Columns. The columns are sorted by the minimum of
`Heatmap Column Sort`, ascending, so grades stay in order (K, 1 to 12) and
subjects follow alphabetically.

No other sheet changes its shelves. `Module - Overall - Teacher` keeps grade
level.

### Completion follows the pivot

Because `Heatmap Column` is in the completion grain, a high school cell in
`Course Subject` mode is one subject at one school across all its grades. That
matches how a high school assessment is given.

### Dashboard actions

The `Grade Heatmap > Others` filter action passes every field of the clicked
heatmap mark to the other sheets. After the change it passes `Heatmap Column`
where it passed grade level. The targets read the same datasource and parameter,
so the filter means the same thing. A click cannot be rendered, so this needs a
human click test in both modes before the copy is promoted.

## Why no dbt change

The extract already has every row (`overall` and not-taken) and every column
(`administered_at`, `subject_area`, `grade_level`, `percent_correct`) the design
reads. Three reasons to stay in the workbook:

- A new extract column would need the datasource's column metadata edited by
  hand and a server-side extract refresh before anything renders. The skill has
  no verified path for that.
- The packaged extract in the review copy can verify a workbook-only change the
  same day. A dbt change waits for a merge, a prod build and a refresh.
- The Cube validation of this dashboard pins this model's SQL. A model change
  makes its comparisons stale for no gain.

Rejected alternative: have the extract label a not-taken row `overall`. It would
revive the old calcs with no workbook edit, but it puts null-score rows on every
sheet of 2 published dashboards and changes student counts on the distribution
sheets.

A dbt change becomes necessary only if a later request needs something the
extract lacks, such as Miami not-taken rows.

## Delivery

- A new review copy, named `ZZ-REVIEW <date> DDI Suite module completion`, in
  the non-production project the user names. The skill's default is
  `GPA-monitor-temp` (`c74d8e08-b856-4430-a759-ebacb061e376`). The base copy is
  never overwritten.
- The copy carries the base's packaged extract, so its data is as of the base's
  last refresh.
- Throwaway probe copies used for verification are deleted when done.
- Edit and check scripts stay in the worktree's gitignored
  `.claude/scratch/tableau/module-dashboard/`. One entry script rebuilds the
  output from a fresh base, so the edits can be replayed if the base changes
  before promotion.
- `docs/models/ddi-stack-data-model.md` gains the completion definition and the
  pivot.

## Verification

- Both checkers (`check_twb.py --ref`, `check_geometry.py --baseline`) pass
  against the untouched base, then against the output.
- Each edit has an assertion that fails on the base, passes on the output and
  catches a deliberately broken variant.
- An independent oracle computes cell completion from the packaged `.hyper` with
  SQL. A probe copy exports the heatmap's data, and the 2 must match exactly, in
  both pivot modes.
- With the completion filter set to 0 in a probe copy, every mastery value on
  the 2 heatmaps equals the base's, except marks that include an assessment not
  yet due.
- Renders of the final copy, cropped, in each `Dashboard View` and each
  `Heatmap Columns` value: no `####`, no literal field token, no overlap,
  columns in order.

A human still has to: open the `.twbx` in Desktop, hover the Assessments Over
Time tooltip, click a heatmap cell in both pivot modes, and move the completion
slider.

## Out of scope

- Publishing to production.
- The other Asana subtasks: the enrollment rule, the WPP filter and the high
  school band grouping.
- Completion on sheets outside the Module Dashboard, beyond the shared calcs
  becoming accurate.
- Miami not-taken rows.
- Reconciling the dashboard's completion with Cube's `pct_taken`, which has no
  administered-date rule.
