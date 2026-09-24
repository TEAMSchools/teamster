# Gotchas and common mistakes

## Gotchas that cost time

- **On the wide sheet, a column without `practice` in its name is official.**
  Practice has its own nine score columns and three attempt counts; the official
  columns were deliberately NOT renamed to `*_official` for symmetry, because
  the model is contract-enforced across 67 columns and feeds a live sheet, so a
  rename changes 40 contract entries and 40 headers under anyone with a formula.
  If you add an administration to the tab, add its practice column too — a
  practice score with no column of its own does not fall back anywhere, it
  simply does not appear.
- **The long sheet's `test_type` column is the scope, not Official/Practice.**
  It is `scope as test_type` in the final select and predates the practice work.
  Official versus Practice lives in `administration_type`. Filtering `test_type`
  expecting the latter silently returns nothing.
- **Anything keyed on score type, season and grade needs test type too.** The
  tab carries practice administrations at the same score type and grade as
  official ones, so a column or filter keyed on those three alone mixes them. It
  looks fine today only because no practice PSAT data exists yet; the wide sheet
  had exactly this latent bug until the score was split by test type in its
  `roster` CTE. This is the same failure that produced 4,107 fabricated practice
  rows on the roster dashboard — the general rule is in _Practice is first-class
  in the strategy_ in [goals.md](goals.md).
- **An attempts score of 0 is not the same as null, and confusing them halves
  every reported percentage.** `_current` reads 0 where a student holds any
  result of that test type but never sat this particular test, and null where
  they hold no result at all. Every attempts metric shares one denominator —
  1,319 of 2,090 enrolled students — so treating a non-tester as 0 moves it to
  2,090 and SAT 1 Attempt reads 20.2% instead of 31.8%. Nothing errors, no row
  count changes, only the denominator moves. Production got this population by
  reading the participation roster, whose grain is enrollment intersected with
  results.
- **Only a total-level Benchmark is grade-specific.** Attempts and section
  thresholds apply to every student regardless of grade. Requiring a grade match
  on Attempts cuts them to a quarter of their rows; letting null-grade rows
  apply to everyone pulls in total-level thresholds that merely lack a goal,
  which inflated Practice totals by 4,028 rows before the rule was narrowed. The
  tell is that `grade_level` is null on exactly the rows where no goal was
  stated.
- **A `KTAF` total on `_current` is Camden and Newark.** The report is high
  school, Paterson has no high school grades, and Miami is not on Illuminate so
  its scores are untrackable. `district` reads KTAF regardless, so the label is
  wider than the population.
- **`_over_time` and `_benchmark_calcs` deliberately disagree on 27 students
  right now.** `_over_time` dropped the `rn_highest = 1` score filter and shows
  their restored SAT scores; `_benchmark_calcs` reads
  `benchmark_aligned_scope_max_score`, which keeps the filter, so the same
  students still read `No Data` there. This is expected until the benchmark view
  is repointed — do not "fix" either side to make them match without reading
  _Known issue — `rn_highest = 1` discards scores_ in the reference doc first.
- **Two different causes move over-time percent-met, and they never overlap.**
  Restored scores land only on grad years 2014, 2015 and 2022; the PSAT 8/9
  800-to-790 threshold lands only on 2028 and 2029. Before explaining a moved
  number, check which grad year it is — attributing a 2029 shift to the restored
  scores, or a 2015 shift to the threshold, is the easy mistake.
- **A restored score flips more rows than there are students.** The
  `met_min_score_int_overall_*` columns are window maxes over partitions
  spanning score types, so one restored SAT score also flips that student's
  `act_composite` row inside the same ACT/SAT-and-Total partition. 13 students
  read as 26 moved rows. Count distinct students, never rows.
- **The BigQuery MCP service account cannot read Google Sheets externals** (no
  Drive scope), and the prod `stg_*` table is frozen at the last build. Query
  the `src_*` external live through ADC with `uv run python`, per
  `.claude/context/bigquery.md`.
- **`rg -ril <pattern>` silently mangles output** — `-r` consumes `il` as a
  replacement string. Use plain `grep`.
- **`WHERE` runs before window functions.** Section rows borrow their score from
  the `overall` sibling via
  `max(if(response_type = 'overall', …)) over (partition by … assessment_id)`,
  and that window must live in the `responses` CTE where both row types exist.
  Computing it in a select that already filters `where response_type = 'Group'`
  returns null on every row, silently — the condition is never true over the
  surviving partition.
- **`scope` now comes from the sheet, not Illuminate.** The hub's `scope` is the
  real test and `test_type` is the constant `Practice`, matching the official
  hub. Illuminate's own scope — `SAT`/`ACT` on AY2023 rows, `Benchmark` on the
  SY26-27 SAT assessments, null on the PSATs — is never read. Every predicate
  selecting a test keys on `scope`; keying on `test_type` matches nothing and
  fails silently.
- `course_discipline` comes from the scaffold (Math is `MATH`, Science `SCI`),
  and the composite is built with `group by`, so ACT composite rows are 1:1 (379
  rows). Older notes flag `NA` math rows and duplicated composites (1,094 rows);
  both are resolved, per the reference doc's impact section.
- **AY2023 grade 9-10 SAT is excluded on purpose — do not re-add it.** KIPP
  Forward ruled those administrations invalid (grades 9-10 should have sat PSAT,
  not a full SAT form). The exclusion lives in the scaffold sheet: all three
  AY2023 SAT Practice rows were deleted (`sat_math`, `sat_ebrw`,
  `sat_total_score`), so the conversion CTE's inner join drops every band. Their
  conversion bands are still in the sheet and are inert. Deleting `sat_math` was
  safe only because grade 11 AY2023 has no data at all — 138849 and 138850
  return zero rows from every Illuminate layer. AY2023 ACT stays and still
  reports 379 composites.
- **`rpt_tableau__college_assessment_dashboard_scores` averages over ALL
  attempts under both Score Category options — that is the design, not a bug.**
  The filter switches the measure between `scale_score` (each attempt's own
  score) and `max_scale_score` (that student's best for the score type); both
  average over the same row set, so a student who tested twice counts twice
  either way. It looks like an attempt-weighting error and it is not. Do not
  "correct" it by filtering `rn_highest = 1` — that would empty the
  `scale_score` option, whose entire purpose is showing every attempt. The
  view's grain is one row per attempt and both measures share it.
- **Deleting a scaffold row is the exclusion mechanism, and it is grade-blind.**
  The conversion-to-scaffold join keys on (`academic_year`, `scope`,
  `score_type`) and deliberately omits grade, so a score type shared across
  grades cannot be excluded for one grade only. A first attempt at the AY2023
  exclusion removed Reading and Writing but left `sat_math`, which grade 11 also
  uses — leaving 737 Total rows with `actual_total_subjects_tested = 1` against
  `expected = 3` and a null score on every one.

## Common mistakes

| Mistake                                                                           | Consequence                                                                           |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Entering `Fall`/`Winter` in `scope_round`                                         | Inconsistent with all 12 legacy rows; `scope_round` becomes a value nothing else uses |
| Entering `Math` instead of `Mathematics`                                          | Breaks the subject join and the total's subject count                                 |
| Using Illuminate's `academic_year` (2027) instead of `academic_year_clean` (2026) | Rows sort into the wrong year                                                         |
| Using `Scale Score Upper`                                                         | Every score inflated ~20 points against history                                       |
| Joining the sheet on `assessment_id` alone                                        | ~50× fan-out — the sheet holds 45–54 rows per assessment                              |
| Giving BOY and MOY the same round value                                           | Their sections sum into one bogus 1600+ total                                         |
| Parsing the paste by column position                                              | Reads `Percentage` as the scale score when a tab lacks `Scale Score Upper`            |
| Treating the prod `stg_*` table as current sheet content                          | Reports pre-edit values indefinitely                                                  |
| Waiting on the sheet source asset in Dagster                                      | It never materializes; you wait forever                                               |
