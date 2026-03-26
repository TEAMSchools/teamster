# State Assessments Rebuild

**Branch:** `claude/feat/stat-rebuild` **Date started:** 2026-03-23 **Status:**
In progress

## Motivation

1. **New reporting requirements** — Demographic comparison reporting that didn't
   previously exist (e.g., state test comparison by demographic subgroups)
2. **Tech debt cleanup** — Assessment models had duplicated business logic
   (proficiency banding, subject mapping, metadata) scattered across reporting
   layers, making them fragile and hard to maintain

## Architectural Pattern

**Push transformation logic upstream, simplify reporting downstream.**

### Proficiency banding

Each assessment source computes standardized proficiency bands in its own
intermediate model rather than in Tableau reporting models:

- **Pearson (NJSLA):** `njsla_aggregated_proficiency` — levels 1-2 = "Below/Far
  Below", 3 = "Approaching", 4+ = "At/Above"
- **FLDOE (FAST):** `fast_aggregated_proficiency` — level 1 = "Below/Far Below",
  2 = "Approaching", 3+ = "At/Above" (FAST uses a 1-5 scale where proficiency
  starts at level 3, vs NJSLA's level 4)
- **iReady:** `iready_proficiency` — same banding pattern as Pearson (levels 1-2
  = Below, 3 = Approaching, 4+ = At/Above)

### Metadata columns

Added at the intermediate layer (not in reporting):

- `results_type` — "Actual" vs "Preliminary"
- `district_state` — "KTAF NJ" or "KTAF FL"
- `illuminate_subject` — standardized subject mapping (ELA = "Text Study",
  Algebra/Geometry = "Mathematics")
- `discipline` — broader category (Math, ELA, Science, Social Studies)

### Demographic alignment

Grade/demographic group mapping moved from reporting into staging:

- `stg_google_sheets__state_test_comparison_demographics` now computes
  `comparison_demographic_group_aligned`,
  `comparison_demographic_subgroup_aligned`, `total_proficient_students`,
  `school_level`, `grade_range_band`, `discipline`, and `season`
- Old `stg_google_sheets__state_test_comparison` disabled (`enabled: false`)
  because the demographics sheet is a superset of the old source

### Reporting simplification

`rpt_tableau__state_assessments_*` models now primarily select pre-computed
columns instead of containing large CASE blocks.

## What's Been Done

### Assessment intermediate models

| Model                              | Changes                                                                                                                                                                                                                                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `int_fldoe__all_assessments`       | Added `achievement_level_int`, `results_type`, `district_state`, `illuminate_subject`, `fast_aggregated_proficiency`                                                                                                                                               |
| `int_pearson__all_assessments`     | Added `illuminate_subject`, `njsla_aggregated_proficiency`, `results_type`, `district_state`, `is_504`, `aligned_test_code`, `race_ethnicity`, `admin`, `season`, `aligned_subject`, `is_proficient_int`. Contract enforcement disabled (temporary dev workaround) |
| `int_pearson__student_list_report` | **New model** — raw transformation layer for Pearson student list data with `performance_band_level`, `is_proficient`                                                                                                                                              |
| `int_iready__diagnostic_results`   | Added `iready_proficiency` column                                                                                                                                                                                                                                  |

### Google Sheets staging

| Model                                                   | Changes                                                                                                                                             |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `stg_google_sheets__state_test_comparison_demographics` | Enhanced with derived columns: `season`, `school_level`, `grade_range_band`, `discipline`, aligned demographic columns, `total_proficient_students` |
| `stg_google_sheets__state_test_comparison`              | Disabled (`enabled: false`)                                                                                                                         |
| `sources-external.yml`                                  | Updated source references; course subject crosswalk sheet range renamed to `_v2`, `Exclude_from_Gradebook` column dropped                           |

### Tableau reporting models (simplified)

| Model                                              | Changes                                                                                                                                                                                                                                                                    |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rpt_tableau__state_assessments_dashboard`         | Switched to demographics source; Student List Report section refactored — `discipline`, `subject`, `test_code`, `performance_band_level`, `is_proficient`, `results_type` all switched from inline CASE/IF to upstream column references                                   |
| `rpt_tableau__state_assessments_dashboard_comps`   | Removed demographic alignment CASE blocks, uses pre-computed columns                                                                                                                                                                                                       |
| `int_tableau__state_assessments_demographic_comps` | Lineage changed from `stg_pearson__student_list_report` to `int_pearson__student_list_report`; `is_proficient_int`, `results_type`, `district_state`, `aligned_test_code` all switched from inline to upstream; `local_student_identifier` now passed through (was `null`) |

### Extracts and base models

| Model                                        | Changes                                                                                |
| -------------------------------------------- | -------------------------------------------------------------------------------------- |
| `int_extracts__student_enrollments_subjects` | Refactored to use upstream proficiency/subject columns instead of inline CASE          |
| `int_extracts__student_enrollments_courses`  | **New model** — course enrollment extract from `base_powerschool__student_enrollments` |
| `base_powerschool__course_enrollments`       | Added `standardized_discipline`; removed `exclude_from_gradebook`                      |

## Known Issues

- `int_pearson__all_assessments` has contract enforcement disabled — needs to be
  re-enabled or documented as intentional before merge
- `int_pearson__student_list_report` properties file is incomplete — no column
  definitions, no uniqueness test (required by project conventions)
- Branch history is messy (merged from `stat` and `int-extracts-courses`
  branches, has checkpoint commits) — should be squash-merged

## What's Still Open

- Add column definitions and uniqueness test to
  `int_pearson__student_list_report.yml`
- Re-enable contract enforcement on `int_pearson__all_assessments` or document
  why it should stay off
- Identify remaining assessment sources and reporting models that need the same
  upstream-migration treatment
- Determine scope of additional demographic reporting needs
- Testing and validation of refactored models against production data

## How to Resume

1. Run `uv sync --frozen` to install dependencies
2. Prepare dbt projects before testing:
   ```bash
   uv run dagster-dbt project prepare-and-package \
     --file src/teamster/code_locations/kipptaf/__init__.py
   uv run dagster-dbt project prepare-and-package \
     --file src/teamster/code_locations/kippmiami/__init__.py
   ```
3. Pick up from "What's Still Open" above
