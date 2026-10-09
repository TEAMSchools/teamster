# Move non-union logic out of 5 kipptaf union models

Refs #5832. Follow-up to #5831.

## Goal

Each of 5 kipptaf union models should only stack district rows. Today they join
other sources or run single-source logic. Move that logic to the layer that owns
it, without changing any consumer's output. A side effect:
`stg_powerschool__schools` and `int_iready__diagnostic_results` no longer have a
reason to stay tables (#5831 can flip them later; this work does not).

## Shipping

2 PRs, in order:

1. **PR 1 — kipptaf only.** `location_key` moves and the Overgrad pivot removal.
   No district model changes, so normal CI applies.
2. **PR 2 — packages.** Star and i-Ready. Adds columns and models to the
   renlearn and iready packages, so it uses the single-PR cross-project workflow
   in `src/dbt/kipptaf/CLAUDE.md` (seed `zz_stg_kippmiami_*` and
   `zz_stg_kippnewark_*`).

## PR 1

### `stg_powerschool__schools`

- kipptaf model becomes `union_relations` plus `_dbt_source_project`. The
  `stg_google_sheets__people__locations` join and the `location_key` column are
  removed.
- The only consumer of `location_key` is `int_students__schools` (domain
  `int_`). Its PowerSchool branch gains the same join the model had:
  `school_number = powerschool_school_id`, `not is_pathways`,
  `location_name <> 'KIPP Whittier Elementary'`. Its Focus branch already joins
  the sheet, so no new layer edge.
- The 8 other consumers never read `location_key`.

### `int_deanslist__incidents`

- kipptaf model becomes `union_relations` plus `_dbt_source_project`. The sheet
  join and `location_key` are removed.
- New domain model `students/intermediate/int_students__behavioral_incidents`, 1
  row per incident: `int_deanslist__incidents` left-joined to the sheet on
  `school_id = deanslist_school_id` with the same 2 filters, adding
  `location_key`. Properties file with the incident-grain uniqueness test the
  union carries today.
- `fct_behavioral_incidents` reads the new model instead of
  `int_deanslist__incidents`. This also removes its existing A1 edge (mart
  reading a source `int_`).
- `rpt_branchingminds__behavior_incident` already reads the sheet. Its join
  changes from `i.location_key = loc.location_key` to
  `i.school_id = loc.deanslist_school_id` plus the 2 filters. In prod, the 25
  non-null DeansList ids are unique after those filters, so no fan-out.
- Rejected: adding `deanslist_school_id` to `dim_locations` (source join id on a
  mart, rubric R8); joining the sheet in the fact (new A1 violation); joining
  `int_people__location_crosswalk` (alias grain, fans out).

### `int_overgrad__students`

- Delete the `choices_long` / `choices_pivot` CTEs and the 3 columns
  `first_choice_school`, `second_choice_school`, `third_choice_school`. Nothing
  in `src/`, Cube, or exposures reads them; `int_overgrad__top_choices` already
  serves top choices.
- The model becomes `union_relations` plus `_dbt_source_project`. Deleting the
  join also removes the `ur.id = c.student__id` join that lacked a
  `_dbt_source_project` match.

### PR 1 verification

- Dev build of every touched model and its direct children.
- Against prod: row count and key-distinct count on `int_students__schools`,
  `fct_behavioral_incidents`, `rpt_branchingminds__behavior_incident`, and
  `int_overgrad__students`; `location_key` matches prod per row on the first
  two.
- The 3 Overgrad columns are the only intended schema change.

## PR 2

### Star

- renlearn package `stg_renlearn__star` gains the decode and cast columns:
  `completed_date_value`, `academic_year`, `grade_level`, `star_subject`,
  `star_discipline`, `subject`, `administration_window`,
  `is_district_benchmark_proficient_int`, `is_state_benchmark_proficient_int`.
  It also filters `deactivation_reason is null` (soft delete, a `stg_` job).
- New package source `int_renlearn__star` reads that `stg_` and adds
  `rn_subject_round` and `rn_subject_year`, partitioned without
  `_dbt_source_relation` (1 relation per district).
- kipptaf `stg_renlearn__star` unions `int_renlearn__star` instead of the
  package `stg_`, and keeps `focus_student_number` and the
  `int_people__location_crosswalk` region lookup (documented pattern). Its 10
  consumers see the same columns.
- Checked in prod: no 2 raw `student_identifier` values map to 1 converted id
  within a year and subject, so ranking on the raw id matches today.

### i-Ready

- New iready package source `int_iready__diagnostic_results` reads the package
  `stg_iready__diagnostic_results` and adds the 8 `max(...) over` windows and
  `rn_subj_year`, partitioned by `student_id, academic_year, subject`.
- kipptaf `int_iready__diagnostic_results` unions the new package model and
  keeps: `focus_student_number`, the `int_people__location_crosswalk` lookup
  (`region`, `school_abbreviation`, `schoolid`, the rewritten
  `_dbt_source_relation`), `state_assessment_type`, and `_dbt_source_project`.
- New domain model
  `assessments/intermediate/int_assessments__iready_diagnostic_results` reads
  the kipptaf union and adds the 6 `stg_google_sheets__iready__crosswalk` joins,
  the `stg_google_sheets__reporting__terms` join, and the columns that depend on
  them: the `projected_*` / `*_with_typical` sets, `proficent_scale_score`,
  `test_round`, `round_number`, `iready_proficiency`,
  `scale_points_to_proficiency`, `progress_to_typical`, `progress_to_stretch`,
  `rn_subj_round`.
- The 13 consumers that read those columns move to the domain model. The 3 that
  don't (`dim_assessments`, `rpt_tableau__mtss_rti`, `rpt_gsheets__mtss_rti`)
  stay on the union.
- `int_iready__domain_unpivot` reads `test_round`, and a source `int_` cannot
  read a domain `int_` (A1). Move it to
  `assessments/intermediate/int_assessments__iready_domain_unpivot` reading the
  domain model; repoint `rpt_tableau__miami_k2_iready` and
  `fct_assessment_scores_enrollment_scoped`. Rename sweep includes
  `*.{sql,yml,md}`.
- Checked in prod: no NJ `(student_id, academic_year, subject)` spans 2 regions
  (225,909 rows), so dropping the region from the window partition matches
  today. Same raw-vs-converted id check as star passed for Miami.

### PR 2 verification

- Seed `zz_stg_kippmiami_renlearn`, `zz_stg_kippmiami_iready`, and
  `zz_stg_kippnewark_iready` by building the modified package models
  `--target staging`; clone the rest.
- Compare the new domain model and kipptaf `stg_renlearn__star` against prod
  `int_iready__diagnostic_results` / `stg_renlearn__star`: row count, key
  distinct count, and a full-row `except distinct` both ways on shared columns.

## Out of scope

- Flipping the 2 tables to views (#5831).
- Region lookups on the shared NJ vendor accounts that the issue lists as
  staying in kipptaf.
- Other existing A1 edges in the touched consumers.
