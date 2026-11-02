# Cube validation: code-group row values

Issue: #6212. Stacked on #6160
(`cristinabaldor/feat/claude-cube-validation-and-build-skill`).

## Intent

The Cube validator proves why a dashboard cell and a Cube cell differ, row by
row. Today it only proves differences in which rows each side holds
(`cube_only`, `dashboard_only`, `dims_differ`), or in plain columns both sides
carry (`value_differs`). It cannot prove a difference that comes from how each
side counts a row both sides hold, when the dashboard side counts with a Tableau
code group inside a calculated field.

The Attendance Dashboard validation hit this on 8 cell sets. A day coded TD is
in both tables with the same code. Tableau's "# Tardy" counts a day when its
code is in the workbook's Tardy group (ET, T, T10, TLE), so TD counts 0. Cube's
`is_tardy` is `att_code like 'T%'`, so TD counts 1. The row reconcile finds
nothing, `triage confirm --cells` cannot size the cells, they stay in
`investigate`, and `review` refuses to run.

The DDI Suite validation (#6211) never hit this: every one of its differences
was a row one side dropped (for example `module_type != 'WPP'` in dbt), and
those are already provable. The rule of thumb: a code filtered out in dbt or by
a sheet filter is a missing row; a code grouped inside a Tableau calc is the
same row counted differently. This feature covers the second.

## Goals

- A comparison can carry a Tableau code group as a row value on the dashboard
  side, so rows where the two sides' rules disagree become `value_differs`
  groups.
- `triage confirm --cells` sizes a count cell from those rows, so the cell set
  can reach `cause` once its groups are proven.
- `review` gives the domain owner one question per measure, showing each side's
  rule and then the codes where the rules disagree.
- The disagreeing codes are checked across every year in the fact table, so
  prior years are covered, not only the run's year.

## Non-goals

- Chronic absenteeism and truancy cells. They are student-level flags, not code
  groups, and need their own design.
- Parsing Cube's rule out of dbt SQL. The comparison's existing `definitions:`
  states each side's rule in words.
- Changing how row-membership differences (the DDI shape) are proven.

## Anti-goals

- A code list typed into the validation YAML. It drifts from the workbook. The
  validator reads the codes from the `.twb`.
- Free SQL in the YAML. Column names stay plain identifiers (`_identifier`), and
  codes are quoted literals the validator builds itself.
- One owner question per code. The owner answers per measure.
- Day counts in anything the owner reads (the issue, its questions JSON). Codes
  only.

## Decided

These were settled with the analyst:

1. The Tableau side's codes come from the workbook's code group, read by the
   validator. Nobody types them.
2. The review shows, per measure, each side's rule first, then the codes where
   the rules disagree. For # Days Absent, Cube's rule is a source field
   (`1 - attendancevalue`), not a code list, so "codes where the rules disagree"
   means the codes found on rows where the two rules give different answers.
   For # Tardy and # OSS both sides are code-based.
3. Codes only, no counts. One question per measure.
4. The disagreeing codes come from every value in the fact table, across all
   years.
5. Built as a follow-on PR stacked on #6160, in its own worktree, linked to
   #6212.
6. % On-Time is in scope: the code-group value supports an inverted form and a
   "present days only" condition (step 4a below).
7. The all-years code check reads the comparison's own rows with only the year
   dropped, not the whole fact table.

## What the analyst sees and does

1. In a comparison's `rows.values`, an entry's dashboard side can name a code
   group instead of a column, for example (shape is the builder's call):

   ```yaml
   rows:
     values:
       - dashboard: att_code
         group: { field: Att Code (group), value: Tardy }
         cube: is_tardy
   ```

2. `prove` reads that group's codes from the workbook copy it exports, and
   records them in the proof, so `prove --check` catches a workbook edit that
   changes the group. `run` never reads the workbook (existing rule), so it uses
   the recorded codes.
3. The row reconcile scores the dashboard side `1` when the column's value is in
   the recorded codes and `0` otherwise, and compares that with the Cube column.
   Rows that disagree land in `value_differs`, grouped as today.
4. The analyst proves the `value_differs` bucket with
   `triage confirm --bucket value_differs`, as today. Each cause names both
   sides' literal rules, for example `att_code like 'T%'` against the Tardy
   group's codes. A proof never types the group's codes: it names the group
   through a placeholder that `confirm` fills from the proof's recorded codes,
   so a committed proof file cannot drift from the workbook (my call). The
   placeholder is part of the proof's fingerprint, so a changed group re-opens
   the proof. 4a. On-time (decided): the group entry also takes an inverted form
   (score `1 − in group`) and a "present days only" condition naming a present
   column on each side, so a non-present day is null on both sides and drops out
   of the rate. With it, `pct_ontime` cells rebuild as the mean of the value
   column over present days, on both sides.
5. `triage confirm --cells` sizes the cell from the per-cell sums the run
   already keeps for the comparison's single value column, not from net rows (a
   row whose value is 0 must add nothing). A count measure rebuilds each side as
   the SUM of that column over the cell's rows; a rate measure as the mean, as
   today. Count or rate comes from the measure's type in Cube meta (my call). A
   comparison that needs this sets its own `rows` with exactly one value column,
   and mirrors its measure's own filters in `scope` (for `count_tardy_days`,
   `membership_value = 1` and `attendance_value` set), since Cube's row query
   carries dimensions only (my call).
6. `review` renders, for each measure whose differences are this kind and
   decided `domain_owner`: the two rules from `definitions:`, then 2 code lists,
   "Cube counts, Tableau doesn't" and "Tableau counts, Cube doesn't". Then one
   question.

## Disagreeing codes across all years

Decided: the check reads the comparison's own rows (its region defaults, `scope`
and measure filters) with only the year dropped. A dashboard that excludes Miami
never shows Miami's codes. The entry therefore also names the code column on the
fact side, since the `cube:` side names the flag.

The Tableau side is a fixed list, so those rows alone answer which codes
disagree, for every year: for each distinct value of the code column, whether
any row has the Cube flag at 1 and whether any has it at 0, compared with
membership in the group. A code the group lists that never occurs in the fact
appears under "Tableau counts, Cube doesn't" only if the builder decides an
absent code is a disagreement; my call is to list it separately as "listed by
Tableau, never seen".

For # Days Absent, Cube counts a code on some days and not others (OSS, M, AE in
the attendance data; partial days are effectively none). My call: mark each such
code "on some days" inside its list rather than adding a third list. The query
reads 2 narrow columns of the fact table and is priced and capped like every
other query.

## Constraints

- Everything owner-facing stays PII-free: codes and rule text only.
- Every query is priced first and counts against the daily cap.
- Tests under `tests/scripts/cube_validation/`, run with
  `uv run pytest tests/scripts/cube_validation/<file>`; never bare
  `uv run pytest`.
- The `cube-validation` skill's runbook (step 3's `rows` text, the cell-set
  paragraph in step 8, and a gotcha on "same row, counted differently") is
  updated with the feature.
- "Codes only" applies to the code lists. The review's existing masked group and
  row counts, example cells and Reproduce blocks stay (my call).
- The questions JSON gains each measure's rules and code lists, so
  `record-answers` (`answers.py`) and the owner's `cube-validation-answers`
  skill are updated with it (my call).
- Probes and `definitions:` that already spell out codes stay as they are: a
  probe that drifts from the workbook already fails `prove` (my call).
- The PR targets #6160's branch until #6160 merges, then `main`.

## Left to the builder

- The exact YAML key names for the group entry, and how the bin is named (the
  Tableau field's caption or internal name).
- How the recorded codes sit in the proof, and how `prove --check` compares
  them.
- How null values compare (a Cube flag that is null, as on Miami Focus rows for
  `is_tardy`, against a dashboard 0).
- Where the all-years code query runs (`run`, `triage` or `review`) and how its
  result is cached.
- The key names for the inverted form and the "present days only" condition.
- How `review` groups comparisons into one question per measure.

## Done when

- The attendance validation's code-group cell sets (absences, tardy, OSS,
  on-time, Team Counts tardy) reach `cause` through `triage confirm --cells`.
- `review` renders each of those measures' rules and disagreeing codes, and one
  question per measure.
- Existing validation files (DDI) prove and run unchanged.
