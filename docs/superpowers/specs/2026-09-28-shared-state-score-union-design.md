# Shared state score union

Refs [#5366](https://github.com/TEAMSchools/teamster/issues/5366), under the
umbrella [#5362](https://github.com/TEAMSchools/teamster/issues/5362).

## Problem

8 kipptaf models each union `int_pearson__all_assessments` with
`int_fldoe__all_assessments`. Each one restates the per-source column mapping
first, and the names drift between sites. The #5364 bug came from that drift.

This change adds 1 table, `int_assessments__state_scores`, that does the union
and the vendor subject crosswalk join once. The 8 sites read it. Each site keeps
its own filters, year offset and output shape.

## What the diagnostic changed

Re-run on `origin/main` at `d6ac8b6575`, 2026-09-28.

- **8 sites, not 9.** #5583 removed the Florida branch from
  `rpt_deanslist__state_test_scores`, so it no longer unions the 2 sources.
- **The pearson side carries Cambium.** 13210 of the 84418 rows in
  `int_pearson__all_assessments` come from `stg_cambium__njsla`,
  `stg_cambium__eoc` and `stg_cambium__njgpa`. Every New Jersey administration
  from Spring 2026 on is Cambium. A `'pearson'` label on the New Jersey side
  would be wrong for a growing share of rows.
- **The issue's baselines are stale.** Every figure quoted from PR #5361 has
  moved, mostly from Cambium AY2025 and from #5585's FLEID re-pick:

  | Check                                                                               | PR #5361     | Prod, 2026-09-28    |
  | ----------------------------------------------------------------------------------- | ------------ | ------------------- |
  | `int_assessments__score_anchors`, `state_nj`                                        | 71996        | 84401               |
  | `int_assessments__score_anchors`, `state_fl`                                        | 22181        | 22467               |
  | `int_extracts__student_enrollments_subjects`, `state_test_proficiency != 'No Test'` | 43810        | 52851               |
  | `rpt_tableau__academic_goals_rollup`, Math rows / non-null `scale_score_state`      | 15852 / 3769 | 15852 / 7746        |
  | `rpt_tableau__academic_goals_rollup`, Reading rows / non-null `scale_score_state`   | 15394 / 3802 | 15393 / 7772        |
  | `fct_assessment_scores_enrollment_scoped`, rows / distinct `assessment_score_key`   | not measured | 15095570 / 15095570 |

  Verification therefore compares against prod at build time, not against stored
  figures. See _Verification_.

- **No `*_unknown` fallback fires.** On prod, 0 rows carry `state_nj_unknown` or
  `state_fl_unknown` as `assessment_type`. #5368 depends on that answer.

## Sequencing

This change ships before
[#5591](https://github.com/TEAMSchools/teamster/issues/5591). #5591 freezes the
Pearson history as an archive, moves Cambium into
`int_cambium__all_assessments`, and adds `int_assessments__state_nj_scores`. It
then swaps 1 `ref()` inside `int_assessments__state_scores`, so the 8 union
sites change only once, here.

#5367 (the benchmark union) follows this change, because both rewrite
`int_assessments__score_anchors` and `fct_assessment_scores_enrollment_scoped`.

## Design

### The model

`src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_scores.sql`

- **Materialization:** `table`, with the default eager automation and no cron. A
  wide union view would be inlined at every reference, which is the BigQuery
  plan-depth problem in `.claude/rules/dbt-models.md`. State scores load a few
  times a year, so eager rebuilds are rare, and no consumer ends up staler than
  it is today.
- **Shape:** a positional `union all` of 2 enumerated selects, 1 per source,
  then 1 left join to
  `stg_google_sheets__assessments__vendor_subject_crosswalk`. No
  `dbt_utils.union_relations`: the column names differ per source, so a rename
  layer would be needed first.
- **Width:** a superset. It carries every column any of the 8 sites reads. New
  Jersey-only columns are `cast(null as <type>)` on Florida rows, which is what
  the sites do today.
- **Values are raw.** `academic_year` is unshifted. Proficiency comes in every
  shape a site reads (boolean, 0/1 ints, aggregated label), and each site
  derives its own output from those.
- **Grain:** `_dbt_source_project`, `state_student_id`, `academic_year`,
  `administration_period`, `raw_subject`. On prod this key is unique for both
  sources: 84418 New Jersey rows and 24269 Florida rows, 0 duplicates and 0 null
  state ids. The properties file declares it as a
  `dbt_utils.unique_combination_of_columns` test.
- **PII:** `student_number` and `state_student_id` are school-facing ids, and
  the scores are student-level results. Tag the model
  `config.meta.contains_pii: true`.

### Columns

`score_source` labels each row's state, `state_nj` or `state_fl`. It replaces a
vendor label, because Cambium rows sit on the New Jersey side. The fact and
`int_assessments__score_anchors` already use these 2 values. The model maps
`score_source` to the crosswalk's `source_system` key (`pearson`, `fldoe`) in
the join predicate, which is the only place that vendor name appears.

| Column                                                                                                                           | New Jersey (`int_pearson__all_assessments`)        | Florida (`int_fldoe__all_assessments`) |
| -------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------- |
| `score_source`                                                                                                                   | `'state_nj'`                                       | `'state_fl'`                           |
| `_dbt_source_relation`                                                                                                           | same name                                          | same name                              |
| `_dbt_source_project`                                                                                                            | same name                                          | same name                              |
| `student_number`                                                                                                                 | `localstudentidentifier`                           | `student_number`                       |
| `state_student_id`                                                                                                               | `cast(statestudentidentifier as string)`           | `student_id`                           |
| `academic_year`                                                                                                                  | same name                                          | same name                              |
| `administration_period`                                                                                                          | `administration_period`                            | `administration_window`                |
| `administration_round`                                                                                                           | `` `admin` ``                                      | `administration_window`                |
| `season`                                                                                                                         | `` `admin` ``                                      | `season`                               |
| `test_date`                                                                                                                      | same name                                          | same name                              |
| `assessment_name`                                                                                                                | same name                                          | same name                              |
| `assessment_type`                                                                                                                | same name                                          | same name                              |
| `results_type`                                                                                                                   | same name                                          | same name                              |
| `district_state`                                                                                                                 | same name                                          | same name                              |
| `raw_subject`                                                                                                                    | `` `subject` ``                                    | `assessment_subject`                   |
| `subject_area`                                                                                                                   | `subject_area`                                     | `assessment_subject`                   |
| `aligned_subject`                                                                                                                | `aligned_subject`                                  | `assessment_subject`                   |
| `illuminate_subject_area`                                                                                                        | `coalesce(x.illuminate_subject_area, raw_subject)` | same                                   |
| `discipline`                                                                                                                     | same name                                          | same name                              |
| `module_code`                                                                                                                    | `module_code`                                      | `test_code`                            |
| `aligned_test_code`                                                                                                              | `aligned_test_code`                                | `test_code`                            |
| `test_grade`                                                                                                                     | `test_grade`                                       | `cast(assessment_grade as int)`        |
| `grade_level_when_assessed`                                                                                                      | `gradelevelwhenassessed`                           | null                                   |
| `scale_score`                                                                                                                    | `testscalescore`                                   | `scale_score`                          |
| `performance_level`                                                                                                              | `testperformancelevel`                             | `performance_level`                    |
| `performance_level_label`                                                                                                        | `testperformancelevel_text`                        | `achievement_level`                    |
| `is_proficient`                                                                                                                  | same name                                          | same name                              |
| `is_proficient_int`                                                                                                              | same name                                          | same name                              |
| `is_approaching_int`                                                                                                             | same name                                          | same name                              |
| `is_below_int`                                                                                                                   | same name                                          | same name                              |
| `aggregated_proficiency`                                                                                                         | `njsla_aggregated_proficiency`                     | `fast_aggregated_proficiency`          |
| `performance_band_group_label`                                                                                                   | `njsla_performance_band_group_label`               | `fast_performance_band_group_label`    |
| `aligned_performance_band_group`                                                                                                 | same name                                          | same name                              |
| `lep_status`, `is_504`, `iep_status`, `race_ethnicity`, `aligned_ml_status`, `aligned_aggregate_ethnicity`, `aligned_iep_status` | same names                                         | null                                   |

`scale_score` is float64 on the New Jersey side and int64 on the Florida side.
The union widens it to float64, which every site gets today already.

2 New Jersey column pairs are identical on prod today, and both columns of each
pair stay anyway:

- `administration_period` and `administration_round`. `admin` normalizes
  `FallBlock` to `Fall`, so a later load could split them.
- `subject_area` and `aligned_subject`.

The kipptaf CLAUDE.md warns about collapsing a column that is a no-op in today's
data. Each extra column in a table is cheap.

On the Florida side, `achievement_level_int` equals `performance_level` on every
prod row. Only `performance_level` is carried, and
`rpt_tableau__academic_goals_rollup` moves to it. The full-row comparison in
_Verification_ proves the move.

### Hash inputs

`fct_assessment_scores_enrollment_scoped` is contract-enforced and Cube reads
it. Both of its state-branch hashes keep their exact inputs:

- `assessment_score_key` hashes `_dbt_source_project`, `student_identifier`,
  `academic_year`, `administration_period`, `subject_area`. `subject_area` maps
  to pearson `subject_area` and fldoe `assessment_subject`, as today.
- `assessment_administration_key` hashes `assessment_type`, `module_code`,
  `academic_year`, `_dbt_source_project`, `administration_period`. `module_code`
  maps to pearson `module_code` and fldoe `test_code`, as today.

`student_identifier` is
`coalesce(cast(student_number as string), state_student_id)` today, but the New
Jersey branch sets `state_student_id` to null. The shared model carries the real
New Jersey state id, so the fact must keep New Jersey's null:
`coalesce(cast(student_number as string), if(score_source = 'state_fl', state_student_id, null))`.
Without that, the 1 Cambium row with a null `localstudentidentifier` would hash
its state id instead.

### Per-site changes

Where the 2 source branches differ only in filters, they collapse into 1
`select` from `int_assessments__state_scores`, with the filters combined under
`score_source`. Where the branches join different tables, both branches stay,
and each reads the shared model filtered by `score_source`. In both cases only
the shared model unions the 2 sources.

| Site                                               | Change                                                                               | Detail                                                                                                                                                                                                                                                                                                                                                                      |
| -------------------------------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `fct_assessment_scores_enrollment_scoped`          | `state_nj`, `state_fl`, `state_all`, `state_union` become 1 CTE                      | Filter `scale_score is not null and (score_source = 'state_fl' or academic_year >= current_academic_year - 7)`. The crosswalk join goes away: `illuminate_subject` reads `illuminate_subject_area`. `source_system` and `score_source` stay as output literals. `student_identifier` per _Hash inputs_.                                                                     |
| `int_extracts__student_enrollments_subjects`       | `prev_yr_state_test` and `prev_yr_state_test_resolved` become 1 CTE                  | Filter `(score_source = 'state_nj' and assessment_name = 'NJSLA') or (score_source = 'state_fl' and scale_score is not null and assessment_name = 'FAST' and administration_period = 'PM3')`. `academic_year + 1` stays here. `subject` reads `illuminate_subject_area`. `statestudentidentifier` reads `state_student_id`.                                                 |
| `rpt_tableau__academic_goals_rollup`               | The 3 state branches of `state_test_union` become 1 `select`. The STAR branch stays. | The year offset becomes `academic_year + if(administration_period = 'PM1', 0, 1)`, so grade-3 PM1 keeps its unshifted year. The New Jersey Algebra-in-grade-8 exclusion reads `grade_level_when_assessed`. The Florida grade test reads `test_grade`. `assessment_type` is `if(score_source = 'state_nj', assessment_name, 'FAST PM3')`. `level` reads `performance_level`. |
| `rpt_gsheets__assessment_roster`                   | `njsla` and `fast` become 1 CTE                                                      | `assessment_source` stays a per-source literal, `'NJSLA'` or `'FAST'`. The per-source year filters combine under `score_source`.                                                                                                                                                                                                                                            |
| `rpt_tableau__state_assessments_dashboard`         | The pearson and fldoe branches of `assessment_scores` become 1 `select`              | Filter `scale_score is not null and (score_source = 'state_fl' or academic_year >= current_academic_year - 7)`. The prelim branch over `int_pearson__student_list_report` stays as it is.                                                                                                                                                                                   |
| `int_assessments__score_anchors`                   | `state_nj_scores` and `state_fl_scores` become 1 CTE                                 | `source_system` is `if(score_source = 'state_nj', 'pearson', 'fldoe')` and `source_type` is `score_source`. Its crosswalk join in `scores_resolved` stays, because 1 join covers all 5 families. #5367 removes it.                                                                                                                                                          |
| `int_tableau__state_assessments_demographic_comps` | Keeps 2 branches                                                                     | The Florida branch derives demographics from `int_extracts__student_enrollments` and filters to Miami. The New Jersey branch reads the `aligned_*` columns and excludes `OD` and `ELA11`.                                                                                                                                                                                   |
| `int_topline__state_assessments_weekly`            | Keeps 2 branches                                                                     | The Florida branch joins `stg_google_sheets__reporting__terms` to resolve the PM window, and the New Jersey branch hardcodes `'Spring'`. Both join on `state_student_id`.                                                                                                                                                                                                   |

The issue's criterion "the crosswalk is joined once for the state family" holds
for 7 of the 8 sites. `int_assessments__score_anchors` keeps its own join until
#5367, and that join gives the same result, because the key is the same.

## Verification

1. **Compare against prod at the same moment.** Build the modified models into
   the dev schema, deferring to prod, so every upstream resolves to the prod
   relation the current models read. Run each comparison right after the build.
   Read `__TABLES__.last_modified_time` on the upstreams before and after, and
   rerun if prod rebuilt one in between.
2. **Full rows, both directions, on all 8 sites.** For each site,
   `EXCEPT DISTINCT` over every column, in both directions, against its prod
   relation must return 0 rows. `count(*)` must match too, because
   `EXCEPT DISTINCT` hides duplicate rows. For the fact that covers all 15.1M
   rows and both hashes. A full-row match catches a subject flip, a moved year
   offset or a lost row, which a per-source count can miss.
3. **The shared model.**
   - The grain test passes.
   - Rows per `score_source` equal the 2 source models' counts at build time.
   - `tests/stg_google_sheets__assessments__vendor_subject_crosswalk__covers_all_sources.sql`
     still passes.
4. **CI.** dbt Cloud CI reads the staging copies, so it proves compilation and
   contracts, not equivalence. Before blaming this change for a latent failure
   in the `state:modified+` sweep, count the same failure in prod.

## Out of scope

- `rpt_gsheets__kippmiami_payout_roster`: 7 fldoe branches and no pearson
  branch, so it is not a union site here.
- `rpt_tableau__miami_fast`: it unions fldoe with iready, which crosses into the
  benchmark family. It waits for #5367.
- The Pearson archive and the Cambium split: #5591.
- Repointing the 2 assessment dims: #5368.
