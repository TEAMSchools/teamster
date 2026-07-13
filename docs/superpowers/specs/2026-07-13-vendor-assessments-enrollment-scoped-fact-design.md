# Vendor Assessments in `fct_assessment_scores_enrollment_scoped` — Design

Implements [#3625](https://github.com/TEAMSchools/teamster/issues/3625): add
iReady, STAR/Renaissance, and DIBELS/Amplify scores to
`fct_assessment_scores_enrollment_scoped`.

## Scope correction

The issue title also names FAST, but FAST is already present via the `state_fl`
branch — `int_fldoe__all_assessments` unions the FAST/FAST_NEW source systems,
and `dim_assessment_administrations` /`dim_assessments` carry `state_fl_fast`
branches. Only iReady, STAR, and DIBELS are in scope.

## Approach

Inline branches (Approach A): each new source gets its own branch in the four
models that every score source must touch, mirroring the existing `state_nj` /
`state_fl` pattern. A consolidating vendor-scores intermediate (Approach B) was
considered and deferred as a later refactor.

Models touched:

1. `int_assessments__resolved_section_enrollments` — score branches so vendor
   scores resolve to a section enrollment
2. `dim_assessment_administrations` — administration grain-projection CTEs
3. `dim_assessments` — assessment grain-projection CTEs
4. `fct_assessment_scores_enrollment_scoped` — union branches + new
   `growth_percentile` contract column
5. `int_renlearn__star_rollup` — additive upstream edits (STAR only)

## Decisions (from brainstorming)

- **Grain**: native attempt grain. iReady = every completed diagnostic; STAR =
  every attempt per screening window; DIBELS = the `Composite`
  `measure_standard` row per benchmark window only (no subskill measures).
- **Contract**: add one nullable numeric column, `growth_percentile`. Existing
  sources carry NULL. No other new columns.
- **STAR proficiency**: state benchmark family (`state_benchmark_category_name`
  / `state_benchmark_proficient`), not district benchmarks — consistent with the
  fact's state-anchored proficiency semantics.

## Column mapping

| fact concept                       | iReady (`int_iready__diagnostic_results`)    | STAR (`int_renlearn__star_rollup`)                                | DIBELS (`int_amplify__all_assessments`)                              |
| ---------------------------------- | -------------------------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------- |
| grain filter                       | every completed diagnostic                   | every attempt (rollup already excludes deactivated)               | `assessment_type = 'Benchmark'` and `measure_standard = 'Composite'` |
| `student_number`                   | `student_id`                                 | `student_display_id`                                              | `student_number`                                                     |
| `academic_year`                    | `academic_year_int`                          | `academic_year`                                                   | `academic_year`                                                      |
| course subject (resolver)          | Reading → `Text Study`, Math → `Mathematics` | ELA → `Text Study`, Math → `Mathematics` (from `star_discipline`) | `Text Study`                                                         |
| `administration_period`            | `test_round`                                 | `screening_period_window_name`                                    | `period` (BOY/MOY/EOY)                                               |
| test/anchor date                   | `completion_date`                            | `completed_date` (upstream edit)                                  | `client_date`                                                        |
| `scale_score`                      | `overall_scale_score`                        | `unified_score`                                                   | `measure_standard_score`                                             |
| `growth_percentile`                | `percentile`                                 | `percentile_rank` (upstream edit)                                 | `measure_percentile`                                                 |
| `proficiency_level`                | `overall_relative_placement`                 | `state_benchmark_category_name`                                   | `measure_standard_level`                                             |
| `is_mastery`                       | `overall_relative_placement_int >= 4`        | `state_benchmark_proficient = 'Yes'`                              | `measure_standard_level_int >= 3`                                    |
| `_dbt_source_project`              | from its rewritten `_dbt_source_relation`    | via location crosswalk on `school_name` (upstream edit)           | `'kipp' \|\| lower(region)`                                          |
| `assessment_type` / `title` (dims) | `iready` / i-Ready Diagnostic                | `star` / STAR                                                     | `dibels` / DIBELS                                                    |
| `module_code` (hash input)         | `subject`                                    | `star_subject`                                                    | `measure_standard` (`Composite`)                                     |

Internal-only fact columns (`response_type*`, `is_replacement`,
`performance_band_label_number`) and `percent_correct` are NULL for all three
sources.

## Upstream additive edits (STAR only)

`int_renlearn__star_rollup` today projects neither a test date, a percentile,
nor any region/project column. Add, additively:

- `completed_date` (exists in `stg_renlearn__star`)
- `percentile_rank` (exists in `stg_renlearn__star`)
- `_dbt_source_project`, derived via `int_people__location_crosswalk` on
  `school_name` → `location_dagster_code_location`. Required because NJ
  districts share one Renaissance instance (`kippnj`), so the staging
  `_dbt_source_relation` cannot identify the district.

iReady and DIBELS intermediates already carry everything needed.

## Resolver changes

Three new score CTEs in `int_assessments__resolved_section_enrollments`, with
`source_type` values `iready`, `star`, `dibels`. Each projects
`(powerschool_student_number, academic_year, administration_period, subject_area, _dbt_source_project, anchor_date)`
where `subject_area` is the course-mapped subject from the table above, then
unions into the existing `scores` CTE. Rows with a NULL anchor date or NULL
student number are dropped (out of scope), matching the state branches.

The two-tier resolution (subject section, then homeroom) and the
`score_grain_key` dedup work unchanged. DIBELS (K–2) mostly resolves via the
homeroom tier. Multiple attempts within one window share a `score_grain_key` and
therefore one resolved section — correct, because the fact joins back at window
grain.

## Dimension changes

One grain-projection CTE per source (`select distinct` over the same
intermediates and filters as the fact branches) in each dim:

- `dim_assessment_administrations`: hash
  `[assessment_type, module_code, administered_date (null), academic_year, _dbt_source_project, administration_period, source_assessment_id (null), test_type (null)]`
- `dim_assessments`: hash
  `[assessment_type, module_code, source_assessment_id (null), test_type (null)]`

Both hashes reuse the models' existing compositions — no hash-change to existing
rows.

## Fact changes

Three new union branches in `fct_assessment_scores_enrollment_scoped`, each
INNER JOINing the resolver on
`(student_number, academic_year, administration_period, course-mapped subject_area, _dbt_source_project, source_type)`
— the same shape as the state branch.

- `assessment_score_key` =
  `[score_source, _dbt_source_project, student_number, academic_year, administration_period, module_code, test_date]`.
  `test_date` is a required hash input here (unlike the state branch) because
  iReady and STAR keep every attempt within a window.
- `assessment_administration_key` = the dim's composition above.
- New contract column `growth_percentile` (numeric, nullable): vendor percentile
  per the mapping table; NULL on the internal and state branches. Added to the
  fact SQL and `properties/fct_assessment_scores_enrollment_scoped.yml`.

## Testing and validation

- Existing fact PK `unique` test must stay green — `test_date` in the score hash
  covers within-window retests.
- Existing `relationships` tests to `dim_assessment_administrations` /
  `dim_assessments` must stay green — guaranteed by identical hash inputs.
- Post-build checks (BigQuery, PR-branch schema): per-source row counts vs the
  source intermediates; resolver hit-rate per source (share of scores that
  resolved to a section); `growth_percentile` population per source.
- Local `dbt build --select <touched models>+ --defer` before push; dbt Cloud CI
  (`state:modified+`) as the gate.

## Out of scope

- FAST (already present — see Scope correction)
- Cube model changes — the column add is non-breaking and new rows flow through
  the existing cube
- The Approach B refactor (consolidating vendor-scores intermediate)
- `fct_assessment_scores_student_scoped` — enrollment-scoped sources only
