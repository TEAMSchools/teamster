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
5. Vendor source models — additive columns (`_dbt_source_project`,
   `illuminate_subject`): `int_iready__diagnostic_results` (iReady),
   `int_amplify__all_assessments` (DIBELS), and `stg_renlearn__star` (STAR — the
   consolidated union view; also gains a DATE `completed_date_value`). The old
   `int_renlearn__star_rollup` was retired in Nov 2025 and stays disabled — see
   the plan's Task 3 correction.

## Decisions (from brainstorming)

- **Grain**: one row per student x subject x administration window x test day
  per source. iReady = every completed diagnostic (deduped to one per day); STAR
  = every attempt (deduped to one per day); DIBELS = the `Composite`
  `measure_standard` row per benchmark window only (no subskill measures).
  Day-grain dedup was adopted during planning after data validation found
  same-day retests and upstream duplicate rows (see _Duplicate findings_).
- **Contract**: add one nullable numeric column, `growth_percentile`. Existing
  sources carry NULL. No other new columns.
- **STAR proficiency**: state benchmark family (`state_benchmark_category_name`
  / `state_benchmark_proficient`), not district benchmarks — consistent with the
  fact's state-anchored proficiency semantics.

## Column mapping

| fact concept                       | iReady (`int_iready__diagnostic_results`)    | STAR (`stg_renlearn__star`)                             | DIBELS (`int_amplify__all_assessments`)                              |
| ---------------------------------- | -------------------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------- |
| grain filter                       | every completed diagnostic                   | every attempt (rollup already excludes deactivated)     | `assessment_type = 'Benchmark'` and `measure_standard = 'Composite'` |
| `student_number`                   | `student_id`                                 | `student_display_id`                                    | `student_number`                                                     |
| `academic_year`                    | `academic_year_int`                          | `academic_year`                                         | `academic_year`                                                      |
| course subject (resolver)          | Reading → `Text Study`, Math → `Mathematics` | Math (`SM`) → `Mathematics`, else `Text Study`          | `Text Study`                                                         |
| `administration_period`            | `test_round`                                 | `screening_period_window_name`                          | `period` (BOY/MOY/EOY)                                               |
| test/anchor date                   | `completion_date`                            | `completed_date_value` (new DATE on staging)            | `client_date`                                                        |
| `scale_score`                      | `overall_scale_score`                        | `unified_score`                                         | `measure_standard_score`                                             |
| `growth_percentile`                | `percentile`                                 | `percentile_rank` (upstream edit)                       | `measure_percentile`                                                 |
| `proficiency_level`                | `overall_relative_placement`                 | `state_benchmark_category_name`                         | `measure_standard_level`                                             |
| `is_mastery`                       | `overall_relative_placement_int >= 4`        | `state_benchmark_proficient = 'Yes'`                    | `measure_standard_level_int >= 3`                                    |
| `_dbt_source_project`              | from its rewritten `_dbt_source_relation`    | via location crosswalk on `school_name` (upstream edit) | `'kipp' \|\| lower(region)`                                          |
| `assessment_type` / `title` (dims) | `iready` / i-Ready Diagnostic                | `star` / STAR                                           | `dibels` / DIBELS                                                    |
| `module_code` (hash input)         | `subject`                                    | `star_subject`                                          | `measure_standard` (`Composite`)                                     |

Internal-only fact columns (`response_type*`, `is_replacement`,
`performance_band_label_number`) and `percent_correct` are NULL for all three
sources.

## Upstream additive edits

Per the marts CLAUDE.md `_dbt_source_project` promotion pattern
([#3142](https://github.com/TEAMSchools/teamster/issues/3142)) and the
`illuminate_subject` precedent in `int_pearson__all_assessments` /
`int_fldoe__all_assessments`, each vendor source model gains two additive
columns so the resolver, dims, and fact all read materialized values instead of
re-deriving them per consumer:

- `_dbt_source_project` — iReady: `extract_code_location()` on its rewritten
  `_dbt_source_relation`; DIBELS: `concat('kipp', lower(region))`; STAR: via
  `int_people__location_crosswalk` on `school_name` →
  `location_dagster_code_location` (required because NJ districts share one
  Renaissance instance, `kippnj`, so the staging `_dbt_source_relation` cannot
  identify the district).
- `illuminate_subject` — the state→course subject mapping: iReady Reading →
  `Text Study`, Math → `Mathematics`; STAR `SM` partition → `Mathematics`, else
  `Text Study` (Reading and Early Literacy both resolve to ELA sections); DIBELS
  constant `Text Study`.

STAR's columns land on `stg_renlearn__star` (the consolidated kipptaf union
view), NOT on `int_renlearn__star_rollup` — that rollup was disabled by the Nov
2025 "consolidate star calcs" refactor and every STAR consumer already reads the
staging model. `stg_renlearn__star` additionally gains `completed_date_value`
(DATE, cast from `completed_date_local`'s first 10 chars); `percentile_rank`,
`unified_score`, `star_subject`, `screening_period_window_name`,
`academic_year`, and the benchmark columns already exist there. This puts a
crosswalk join in a staging model (a layering trade-off), accepted because the
model is functionally a kipptaf-level union view and it is the single promotion
point.

## Duplicate findings (data-verified during planning)

- **iReady**: `stg_iready__diagnostic_results` has NO uniqueness test. At the
  proposed PK grain (project, student, year, round, subject, day), 3,835
  duplicate groups exist (up to 16 rows/group): ~2,500 are same-day retests with
  different scores; ~1,300 are byte-identical duplicate rows. Fact branch
  dedupes at PK grain, `order_by="start_date desc, scale_score desc"`, with a
  TODO naming the upstream fix (follow-up issue).
- **STAR**: `stg_renlearn__star` holds ~2,300 duplicated `assessment_id`s — 100%
  cross-`_dagster_partition_fiscal_year` re-pulls, identical in every data
  column — plus ~144 same-day multi-attempts. Fact branch dedupes at PK grain,
  `order_by="scale_score desc, assessment_id desc"`, with a TODO (follow-up
  issue).
- **DIBELS**: verified unique at PK grain (55,221 = 55,221). No dedupe.

## Resolver changes

Three new score CTEs in `int_assessments__resolved_section_enrollments`, with
`source_type` values `iready`, `star`, `dibels` (added to the `source_type`
`accepted_values` test in its properties yml). Each projects
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

Three vendor CTEs (with the iReady/STAR dedupes above) union into one
`vendor_all` CTE — the same shape the state branches use (`state_nj` +
`state_fl` → `state_all`) — and one new final union branch INNER JOINs the
resolver on
`(student_number, academic_year, administration_period, illuminate_subject = subject_area, _dbt_source_project, score_source = source_type)`.

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
- File follow-up issues (with user approval) for the two upstream duplicate
  sources: missing uniqueness test / duplicate rows in
  `stg_iready__diagnostic_results`, and fiscal-year re-pull overlap in
  `stg_renlearn__star`. The fact dedupe TODOs reference these issues.

## Out of scope

- FAST (already present — see Scope correction)
- Cube model changes — the column add is non-breaking and new rows flow through
  the existing cube
- The Approach B refactor (consolidating vendor-scores intermediate)
- `fct_assessment_scores_student_scoped` — enrollment-scoped sources only
