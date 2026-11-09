# PM reporting for the AY2026 Grow coach rubric

Issue: [#6253](https://github.com/TEAMSchools/teamster/issues/6253). Branch:
`kevinverhoff/fix/claude-pm-ay2026-rubric`.

## Why

SchoolMint Grow's AY2026 coach scoring rubric ("Coach Reflection: Part 1 -
Scores") replaced the 8 Self & Others (S&O) measures with 7 core-value measures
and added 6 unscored goals. PM outlier detection and the teacher development
dashboard still expect last year's rubric:

- Outlier detection shows nothing for AY2026: both outlier models filter on the
  old rubric names, and the Python script drops every row with a null, which is
  every AY2026 row because `so1`–`so8` are empty.
- The outlier dashboard model has duplicate rows (4,733 rows for 3,326 keys),
  from before this year.
- Teacher development counts the new core values inside its ETR average, and its
  teacher-in-residence (TIR) S&O average and 80/20 PM score go blank.

PM completion tracking and final PM scores and tiers are unaffected: final
scores use Grow's own form score.

## How Grow scores the AY2026 form

Measured against every PMS form in prod:

- AY2025: form score = 80% average of ETR measures + 20% average of the 8 S&O
  measures (1,629 of 1,629 forms).
- AY2026: form score = 80% average of ETR measures + 20% average of the 5
  measures in the "Values" strand: Excellence, Fun, Kid Focus, Radical Love,
  TEAM (39 of 39 forms). Presence and Punctuality (strand "Professionalism and
  Punctuality") are scored on the form but are not in the form score.
- AY2023 ("Coach ETR") and AY2024–25 ("Coach ETR and Reflection: Part 1 -
  Scores") score the same measure set: ETR1A–ETR5C plus S&O-01–08.

## Goals

1. Outlier detection runs for AY2026, fitting on every scored measure for that
   year's rubric: ETR plus all 7 core values (including Presence and
   Punctuality).
2. A global fit only compares observer-rounds scored on the same measure set:
   AY2023–25 (ETR + S&O) together as today, AY2026+ (ETR + core values)
   together.
3. `rpt_tableau__pm_outlier_detection` is unique on (observer_employee_number,
   academic_year, reporting_term, teacher_employee_number).
4. Teacher development follows Grow:
   - ETR averages include only ETR measures, from AY2023 on.
   - A new Values average (the 5 "Values" measures) is reported as its own
     columns.
   - The TIR 80/20 score (`tir_pm*`) reproduces Grow's form score: 80% the
     average of every ETR measure, 20% S&O through AY2025 and Values from
     AY2026.
   - Presence, Punctuality, and goals stay out of every teacher development
     average.

## Non-goals

- Changing final PM scores, tiers, or round completion tracking.
- Changing how the script handles observers with a blank measure (see
  _Constraints_).
- Editing the Tableau workbooks. New columns appear in the extracts; adding them
  to a sheet is a workbook change outside this repo.
- Adding a dbt exposure for the outlier dashboard (it has none today).

## Anti-goals

- AY2023–25 outlier results must not change, apart from the dedup. Their measure
  set and fit population stay exactly as today.
- AY2018–22 teacher development values must not change.

`tir_pm*` for AY2023–25 does change, deliberately: today it averages only ETR
strands 1–3 and matches Grow's form score on 76 of 171 TIR rounds in AY2024 and
18 of 150 in AY2025 (about 0.12–0.18 higher on average). After this change it
matches Grow.

## Approaches considered

For getting the new measures to the Python script:

1. **Wide columns (chosen).** Add 7 named core-value columns next to
   `so1`–`so8`, plus a column naming each row's measure set. The script groups
   by measure set and fits on the columns that set scores. Smallest change to a
   pipeline that already works by column; the dashboard shows each measure by
   name.
2. Long input. The extract sends one row per observer, round, and measure; the
   script pivots per measure set. Future-proof against new rubrics, but rewrites
   the extract and script input, and the outputs still need named columns for
   Tableau.
3. Reuse `so1`–`so8` as generic slots. Rejected: different measures under one
   name would mislead dashboard readers.

Kevin chose wide columns "for now"; a later rubric change may justify the long
input.

For teacher development there was one sensible way: select measures by Grow's
strand and name prefix instead of `like '%S&O%'`.

## Design

### Starting point: #6250

Bring over the 2 commits from `cristinabaldor/fix/claude-pm-rubric-type-codes`
(#6250, closed unmerged, CI green):

- Select PM scoring forms by `observation_type_abbreviation in ('PM', 'PMS')`
  instead of rubric name in `rpt_python__manager_pm_averages` and
  `rpt_tableau__pm_outlier_detection`.
- Dedup the outlier dashboard: `round_end_dates` collapses region end dates to
  `max(end_date)` per (academic_year, code); `score_aggs` groups by key only and
  joins the teacher's primary roster row at their last observation.
- Grain tests on both `rpt_` models (#5990) and on
  `stg_performance_management__outlier_detection`; descriptions; `contains_pii`
  on name and employee-number columns; CRLF→LF.

The branch is 138 commits behind main; bring the commits onto this branch rather
than reviving it.

### `rpt_python__manager_pm_averages` (the script's input)

- Pivot 7 more measures: `excellence`, `fun`, `kid_focus`, `presence`,
  `punctuality`, `radical_love`, `team` (shortnames `EXCELLENCE`, `FUN`,
  `KID FOCUS`, `PRESENCE`, `PUNCTUALITY`, `RADICAL LOVE`, `TEAM`). Goals are
  unscored and already excluded by `row_score is not null`.
- Add `measure_set`: `etr_values` for an observer-round with any core-value
  score, otherwise `etr_so`. Derive it from which measures carry scores (Grow
  strand or measure names), not from a year literal, so a late AY2026 form on an
  old rubric would still group correctly. An observer-round averaged over both
  rubrics is `etr_values`; its S&O columns are ignored by its fit.
- Update the YAML contract and descriptions for the new columns.

### Python asset `performance_management/outlier_detection`

- Fit columns per measure set: ETR1A–ETR5C plus `so1`–`so8` for `etr_so`; ETR
  plus the 7 core-value columns for `etr_values`.
- Fit each measure set present in the partition separately. Global fit: every
  row of that set, across all years. Current fit: the partition's rows of that
  set, on its columns.
- A group too small to fit (PCA needs 2 rows, DBSCAN `min_samples=3`) still
  emits its rows, with null outlier columns for that fit, so the run does not
  fail.
- Blank handling: drop a row only when it is missing one of its own measure
  set's columns (today's behavior, scoped to the set). A row is never dropped
  for being blank on the other set's columns.
- Add the 7 columns and `measure_set` to the `OutlierDetection` Pydantic model
  in `src/teamster/libraries/performance_management/schema.py`.
- Put the column-selection and grouping logic in a pure helper that a unit test
  can import without the dbt manifest (see `src/teamster/CLAUDE.md`: code
  location asset modules need the manifest; `libraries/` does not).

### `stg_performance_management__outlier_detection` and `rpt_tableau__pm_outlier_detection`

- Carry the 7 core-value columns and `measure_set` through both, with contract
  columns and descriptions.

### `rpt_tableau__teacher_development`

- `pm_etr` (`smg_etr_pm*`): from AY2023 on, average ETR measures only, so core
  values, Presence, Punctuality, and goals fall out. AY2018–22 keep today's
  filter (`not like '%S&O%'`), which counts their scored "Comments" strand rows.
- `tir_etr` (`tir_etr_pm*`): unchanged as a displayed column (ETR strands 1–3),
  restricted to ETR measures from AY2023 on.
- New `tir_values` CTE: PMS rows in the "Values" strand, averaged per round,
  joined with the same `srh.job_title = 'Teacher in Residence'` filter as
  `tir_so`. New columns `tir_values_pm1`–`pm3`.
- `tir_pm1`–`pm3` = (average of every ETR measure) × 0.8 + (S&O, or Values when
  there is no S&O) × 0.2, for TIRs. The 80% side no longer reads `tir_etr`; it
  needs an all-ETR average joined for TIRs (the AY2023+ `pm_etr` average
  restricted by the TIR join is one way).
- Update the YAML contract and descriptions.

## Constraints

- **Rollout order.** The outlier Avro files are read through an external table
  (`sources-external.yml`, `metadata_cache_mode: MANUAL`). Old files lack the
  new columns. After deploy, every outlier partition must be re-run (the global
  fits change for AY2026 anyway and the new columns must exist in every file),
  then the external table refreshed, before the staging view can read the new
  columns. The builder confirms how BigQuery picks the Avro schema across files
  and whether staging fails or nulls in between. The re-run is a partition-range
  backfill handed to Kevin in the Dagster UI (root CLAUDE.md _Never_ block).
- **Partitions.** `<year>|PM1-3` for 2023 through `CURRENT_FISCAL_YEAR - 1`;
  AY2026 is covered.
- **Small AY2026 sample.** 8 observer-rounds today, all PM2. The AY2026 global
  fit equals the current fit until more rounds arrive.
- **Blank measures.** Keeping today's drop-the-row behavior drops 2–38
  observer-rounds per round in past years, and 1 of 8 in AY2026 (no Presence or
  Punctuality score). Changing that would move past years' results; it is a
  possible follow-up, not part of this work.
- dbt conventions: `.claude/rules/dbt-sql.md` (S10 on any new multi-condition
  filter, S20 on literals), `.claude/rules/dbt-yaml.md`.

## Decided by Kevin

- Fit outlier detection on all measures the year's rubric scores.
- Global fit only within one rubric's measure set.
- Values take the S&O 20% slot; follow Grow's formula exactly (5 Values, not
  Presence or Punctuality).
- Report Values as new, separate columns.
- Wide columns for the script input.
- `tir_pm*` matches Grow: 80% side averages every ETR measure, changing past TIR
  scores.
- The ETR-only filter applies from AY2023; AY2018–22 stay as they are.

## Calls made in design (Kevin reviewed)

- Group by measure set rather than rubric name, so AY2023–25 keep fitting
  together.
- `measure_set` derived from scored measures, not a year cutover; any core-value
  score makes an observer-round `etr_values`.
- Keep the drop-on-blank behavior, scoped to the row's own measure set.
- A group too small to fit emits rows with null outlier columns.
- Values reported for TIRs only, with the same job-title join as S&O.
- Column names `excellence`, `fun`, `kid_focus`, `presence`, `punctuality`,
  `radical_love`, `team`, `measure_set`.

## Left to the builder

- Exact SQL shape of `measure_set` and the ETR-only filter (S10: a named column
  if the condition is compound).
- Test shape for the Python helper.
- Verification queries: AY2023–25 outlier rows unchanged apart from dedup; the
  `rpt_tableau__pm_outlier_detection` grain test passes; AY2018–22 teacher
  development values unchanged; AY2024–26 `tir_pm*` equals `pm*` (Grow's form
  score) for TIRs where both exist.

## Done when

- `stg_performance_management__outlier_detection` has AY2026 rows after the
  partitions re-run.
- `rpt_tableau__pm_outlier_detection` passes its grain test.
- AY2026 teacher development ETR averages contain only ETR measures, and
  `tir_values_pm*` and `tir_pm*` are populated for AY2026 TIRs.
