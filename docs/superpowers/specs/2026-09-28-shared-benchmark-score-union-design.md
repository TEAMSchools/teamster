# Shared benchmark score union

Refs [#5367](https://github.com/TEAMSchools/teamster/issues/5367), under the
umbrella [#5362](https://github.com/TEAMSchools/teamster/issues/5362). Sibling
of [#5366](https://github.com/TEAMSchools/teamster/issues/5366), whose spec
(`2026-09-28-shared-state-score-union-design.md`) this one follows.

## Problem

`fct_assessment_scores_enrollment_scoped`, `int_assessments__score_anchors` and
`rpt_gsheets__assessment_roster` each map `int_iready__diagnostic_results`,
`stg_renlearn__star` and `int_amplify__all_assessments` into a common score
shape before they union them. Each restates the same per-source column mapping.

This change adds 1 table, `int_assessments__benchmark_scores`, that does the
mapping, the union and the vendor subject crosswalk join once. The 3 sites read
it. Each site keeps its own filters, dedupes and output shape.

## What the diagnostic changed

Re-run on `origin/main` at `22c4c9d876`, 2026-09-28.

- **The fact no longer ranks iReady across grains.** `iready_all_raw`,
  `iready_all_raw_ranked` and the `row_number()` the issue describes are gone.
  `iready_scores` is now a plain `union all` of overall rows and domain rows.
  The domain rows come from `int_iready__domain_unpivot`, a different model, so
  the fact's domain branch does not restate the benchmark union. It stays in the
  fact (the issue's option 1), and that leaves no duplicated mapping behind.
- **`int_iready__domain_unpivot` has 2 consumers, not 1.**
  `rpt_tableau__miami_k2_iready` was added. That weakens the issue's option 2
  further.
- **3 of the issue's 6 sites do not restate the union.**
  - `rpt_gsheets__kippmiami_payout_roster` is disabled (`enabled: false`). Its
    Star branches filter on `rn_subj_round`, which exists only on the disabled
    `int_renlearn__star_rollup`, so it would not compile if re-enabled.
  - `rpt_tableau__miami_fast` does not union these sources. `scale_crosswalk` is
    literal arrays that nothing references. iReady is a left join on 17
    diagnostic-only columns (growth measures, lexile, projections).
  - `rpt_tableau__academic_goals_rollup` reads columns that exist in 1 source
    each: iReady projected levels and typical growth, Star district and state
    benchmark category levels. A shared model would mirror them without sharing
    anything.
- **DIBELS carries 2 grains in its own source.** The fact reads every Benchmark
  measure (`Composite` as `overall`, the rest as `group`).
  `int_assessments__score_anchors` and the roster read `Composite` only.
- **The issue's baselines are stale.**

  | `int_assessments__score_anchors` rows | PR #5361 | Prod, 2026-09-28 |
  | ------------------------------------- | -------- | ---------------- |
  | `iready`                              | 264885   | 265111           |
  | `dibels`                              | 62491    | 63877            |
  | `star`                                | 7966     | 8121             |

  Verification therefore compares against prod at build time. See
  _Verification_.

## Sequencing

#5366 ships first. Both rewrite `int_assessments__score_anchors` and
`fct_assessment_scores_enrollment_scoped`. This spec lands now; the SQL rebases
onto `main` after #5366 merges.

## Design

### The model

`src/dbt/kipptaf/models/assessments/intermediate/int_assessments__benchmark_scores.sql`

- **Materialization:** `table`, default eager automation, no cron, as in #5366.
  A wide union view would be inlined at every reference, which is the BigQuery
  plan-depth problem in `.claude/rules/dbt-models.md`. Both mart-side consumers
  are tables already.
- **Shape:** a positional `union all` of 3 enumerated selects, 1 per source,
  then 1 left join to `stg_google_sheets__assessments__vendor_subject_crosswalk`
  on `source_system` and `raw_subject`.
- **Rows:** as raw as the 3 sites allow.
  - iReady: every row of `int_iready__diagnostic_results` (267363 on prod).
  - Star: every row of `stg_renlearn__star`, before any dedupe (8287).
  - DIBELS: `int_amplify__all_assessments` where
    `assessment_type = 'Benchmark'`, every measure (344789). PM rows stay out:
    no site in scope reads them, and `int_amplify__pm_met_criteria*` are out of
    scope.
- **Filters stay at the sites.** The sites disagree: the fact drops iReady rows
  with `rn_subj_day > 1` (2252 on prod) and with a null `_dbt_source_project`
  (130), and `int_assessments__score_anchors` keeps both. Moving any filter into
  the shared model would change 1 site's rows.
- **Grain:** `score_source`, `_dbt_source_project`, `student_number`,
  `academic_year`, `administration_period`, `raw_subject`, `test_date`,
  `response_type_code`, `rn_subj_day`, `assessment_id`. `rn_subj_day` separates
  iReady same-day retests and `assessment_id` separates Star ones; each is null
  in the other sources. On prod the key is unique for all 3 sources, 0
  duplicates. The properties file declares it as a
  `dbt_utils.unique_combination_of_columns` test.
- **PII:** student ids and student-level results. Tag the model
  `config.meta.contains_pii: true`.

### Columns

| Column                      | iReady                                             | Star                                 | DIBELS                                                   |
| --------------------------- | -------------------------------------------------- | ------------------------------------ | -------------------------------------------------------- |
| `score_source`              | `'iready'`                                         | `'star'`                             | `'dibels'`                                               |
| `source_system`             | `'iready'`                                         | `'renlearn'`                         | `'amplify'`                                              |
| `_dbt_source_project`       | same name                                          | same name                            | same name                                                |
| `student_number`            | `student_id`                                       | `student_display_id`                 | `student_number`                                         |
| `academic_year`             | `academic_year_int`                                | `academic_year`                      | `academic_year`                                          |
| `administration_period`     | `test_round`                                       | `screening_period_window_name`       | `period`                                                 |
| `test_date`                 | `completion_date`                                  | `completed_date_value`               | `client_date`                                            |
| `raw_subject`               | `` `subject` ``                                    | `_dagster_partition_subject`         | `'DIBELS'`                                               |
| `module_code`               | `` `subject` ``                                    | `star_subject`                       | `'Composite'`                                            |
| `illuminate_subject_area`   | `coalesce(x.illuminate_subject_area, raw_subject)` | same                                 | same                                                     |
| `discipline`                | `discipline`                                       | null                                 | null                                                     |
| `scale_score`               | `cast(overall_scale_score as numeric)`             | `cast(unified_score as numeric)`     | `cast(measure_standard_score as numeric)`                |
| `national_percentile`       | `cast(percentile as numeric)`                      | `cast(percentile_rank as numeric)`   | `cast(measure_percentile as numeric)`                    |
| `proficiency_level`         | `overall_relative_placement`                       | `state_benchmark_category_name`      | `measure_standard_level`                                 |
| `proficiency_level_int`     | `overall_relative_placement_int`                   | null                                 | `measure_standard_level_int`                             |
| `is_mastery`                | `overall_relative_placement_int >= 4`              | `state_benchmark_proficient = 'Yes'` | `measure_standard_level_int >= 3`                        |
| `is_proficient`             | `is_proficient`                                    | null                                 | `aggregated_measure_standard_level = 'At/Above'`         |
| `response_type`             | `'overall'`                                        | `'overall'`                          | `if(measure_standard = 'Composite', 'overall', 'group')` |
| `response_type_code`        | null                                               | null                                 | `measure_standard` when not `Composite`                  |
| `response_type_description` | null                                               | null                                 | `measure_name` when not `Composite`                      |
| `rn_subj_day`               | same name                                          | null                                 | null                                                     |
| `rn_subj_round`             | same name                                          | null                                 | null                                                     |
| `assessment_id`             | null                                               | same name                            | null                                                     |

Every expression is the one a site uses today. The fact supplies `module_code`,
`scale_score`, `national_percentile`, `proficiency_level`, `is_mastery` and the
3 `response_type*` columns. The roster supplies `discipline`,
`proficiency_level_int`, `is_proficient` and `rn_subj_round`.

`is_mastery` and `is_proficient` are 2 proficiency definitions: the fact's and
the roster's. They agree on every prod row today (0 of 267363 iReady rows, 0 of
63877 DIBELS `Composite` rows). Both stay. Unifying them is a behavior decision,
not a refactor, and belongs in its own issue.

### Hash inputs

`fct_assessment_scores_enrollment_scoped` is contract-enforced and Cube reads
it. Both vendor-branch hashes keep their exact inputs:

- `assessment_score_key` hashes `score_source`, `_dbt_source_project`,
  `student_number`, `academic_year`, `administration_period`, `module_code`,
  `test_date`, `response_type_code`.
- `assessment_administration_key` hashes `score_source`, `module_code`,
  `academic_year`, `_dbt_source_project`, `administration_period`.

Each input has 1 type across all 3 sources on prod (`student_number` and
`academic_year` INT64, `administration_period` and `module_code` STRING,
`test_date` DATE), so the union widens nothing a hash reads.

### Per-site changes

| Site                                      | Change                                                                                          | Detail                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_assessment_scores_enrollment_scoped` | `iready_scores_raw` and `dibels_scores` become 1 CTE. `star_scores_raw` reads the shared model. | Filter iReady `rn_subj_day = 1 and _dbt_source_project is not null and test_date is not null and scale_score is not null`, DIBELS `test_date is not null`, Star `test_date`, `scale_score` and `_dbt_source_project` not null, each under `score_source`. The Star `dbt_utils.deduplicate` and its comment stay unchanged. `iready_domain_scores_raw` stays and keeps a crosswalk join of its own; the other rows read `illuminate_subject_area`. |
| `int_assessments__score_anchors`          | `iready_scores`, `star_scores` and `dibels_scores` become 1 CTE                                 | Each source keeps its current filter under `score_source`. DIBELS `measure_standard = 'Composite'` becomes `response_type = 'overall'`, the same 63877 rows. With #5366's `int_assessments__state_scores` in place, every non-internal branch reads `illuminate_subject_area`, so the `scores_resolved` crosswalk join is removed. Internal rows keep `raw_subject`, as they do today when they miss the join.                                    |
| `rpt_gsheets__assessment_roster`          | `iready` and `dibels_filtered` read the shared model                                            | Filters unchanged. iReady `discipline in ('ELA', 'Math')` and `rn_subj_round = 1`; DIBELS `response_type = 'overall'`; both keep the 2-year window. The DIBELS `dbt_utils.deduplicate` stays at the roster. Output literals (`'i-Ready'`, `'DIBELS'`, `'ELA'`) stay.                                                                                                                                                                              |

The issue's criterion "exactly 1 model unions the 3 sources" holds with 1 named
exception: the fact unions `int_iready__domain_unpivot` domain rows onto the
shared model's rows. That branch reads a different model at a different grain,
and it keeps its own crosswalk join.

The Star dedupe stays in the fact. `int_assessments__score_anchors` reads Star
undeduped and keeps rows pulled under 2 academic years; the dedupe would
collapse them. The fact is the only site whose grain has no attempt dimension.

## Verification

1. **Compare against prod at the same moment.** Build the shared model and the 3
   sites into the dev schema, deferring to prod. Read
   `__TABLES__.last_modified_time` on the upstreams before and after, and rerun
   if prod rebuilt one in between.
2. **Full rows, both directions, on the 3 sites.** For each site,
   `EXCEPT DISTINCT` over every column, in both directions, against its prod
   relation returns 0 rows, and `count(*)` matches. For the fact that covers
   both hashes on every row.
3. **The shared model.**
   - The grain test passes.
   - Rows per `score_source` equal the source counts at build time, with the
     DIBELS count taken under `assessment_type = 'Benchmark'`.
   - `tests/stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources.sql`
     still passes.
4. **CI.** dbt Cloud CI proves compilation and contracts, not equivalence.
   Before blaming this change for a failure in the `state:modified+` sweep,
   count the same failure in prod.

## Out of scope

- `rpt_tableau__academic_goals_rollup` and `rpt_tableau__miami_fast`: they read
  source-specific columns, so there is no shared mapping to remove. The dead
  `scale_crosswalk` CTE in `rpt_tableau__miami_fast` is left alone.
- `rpt_gsheets__kippmiami_payout_roster`: disabled.
- `int_iready__domain_unpivot` and its domain rows: they stay a fact-only
  branch.
- `int_amplify__pm_met_criteria` and `int_amplify__pm_met_criteria_aimline`.
- `int_reporting__promotional_status`, `rpt_tableau__mtss_rti` and
  `rpt_gsheets__mtss_rti`: they join these sources rather than union them.
- The 2 assessment dims: #5368.
