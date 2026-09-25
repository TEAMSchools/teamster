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
- **Every percentage on the current view divides by all students in the group,
  testers or not.** The workbook filters `_current` to currently enrolled,
  non-IEP-exempt students and divides `met_min_score_int = 1` by all rows; a
  student with no score counts as not met. Verified against the published
  Landing Page bar counts. `score` reads 0 versus null on Attempts rows
  depending on whether the student has any result of that test type, but that
  only matters when averaging `score`.
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
- **`_over_time` and `_benchmark_calcs` disagree on a few dozen historical SAT
  students.** `_over_time` reads scores with no `rn_highest = 1` filter;
  `_benchmark_calcs` reads `benchmark_aligned_scope_max_score`, which keeps it,
  so those students read `No Data` there. It is a known issue to fix, not a
  design choice: see _`rn_highest = 1` hides some students' best scores_ in the
  reference doc before touching either side.
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
  both are resolved, per [rebuild-2026-changes.md](rebuild-2026-changes.md).
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
- **CARAT's SAT is kippadb's SAT, not College Board's.** The College Board SAT
  files reach CARAT only after the data team loads them into Salesforce from the
  Unified KFWD Processes Document (doc _How official SAT reaches the
  dashboard_). When a SAT score is questioned, reconcile the two sources before
  touching a model. Report counts only:

  ```sql
  with
      cb as (
          select distinct
              powerschool_student_number as sn, sat_date as d, sat_total as score,
          from `teamster-332318.kipptaf_collegeboard.int_collegeboard__sat_unpivot`
          where powerschool_student_number is not null and sat_total is not null
      ),

      sf as (
          select distinct school_specific_id as sn, `date` as d, score,
          from `teamster-332318.kipptaf_kippadb.int_kippadb__standardized_test_unpivot`
          where
              score_type = 'sat_total_score'
              and `date` is not null
              and school_specific_id is not null
      )

  select
      extract(year from coalesce(cb.d, sf.d)) as test_year,
      countif(cb.score = sf.score) as both_same,
      countif(cb.score != sf.score) as both_different,
      countif(sf.sn is null) as college_board_only,
      countif(cb.sn is null) as kippadb_only,
  from cb
  full join sf on cb.sn = sf.sn and cb.d = sf.d
  group by test_year
  ```

  Baseline on 2026-09-25, sittings dated July 2024 to June 2026: 1,649 scores in
  both, 1 with different values, 2 College Board scores not yet loaded, and 62
  kippadb-only scores (sittings whose reports didn't come to the school, or hand
  entries). `both_different` and `college_board_only` are the ones to chase; the
  second should match what's on the KIPP Forward SAT sheets. `kippadb_only` is
  expected and needs a look only when a specific score is questioned.

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
