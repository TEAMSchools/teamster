# Column-naming audit execution — bundled PR design

## Summary

Execute the column-naming audit decisions (GitHub #3643, Tier 1) in a single PR
that also resolves the two upstream deduplication blockers (#3633, #3637) so the
mart-layer `SELECT DISTINCT` workarounds can be removed as part of the same
change. All audit decisions are finalized in
[`2026-04-15-column-naming-audit-inventory.csv`](2026-04-15-column-naming-audit-inventory.csv)
and the rubric and structural posture are documented in
[`2026-04-15-column-naming-audit.md`](2026-04-15-column-naming-audit.md). This
spec covers the execution plan only — all column-level decisions are frozen.

## Scope

One PR combining three project-#4 issues:

- **#3643** (Tier 1 — column renames): apply the 170 renames, 180 removes, and
  Groups 1 + 2 of the 25 structural adds (R9 enablers and simple fact-to-dim
  moves) from the audit inventory.
- **#3633** (Tier 2 — broad correctness): deduplicate
  `int_people__location_crosswalk` upstream so the 8 mart models that carry
  `SELECT DISTINCT` workarounds can drop them.
- **#3637** (Tier 2 — broad correctness): deduplicate
  `stg_people__employee_numbers` upstream so `dim_staff` can drop its
  `SELECT DISTINCT` + `-- TODO: #3637` workaround.

### Structural adds split

Of the 25 audit-approved structural adds, **Groups 1 + 2 (~22 rows) ship in this
PR; Group 3 (3 rows) defers**.

- **Group 1 — R9 enablers (required to support removes)**: `region_key` on
  `dim_locations` / `dim_terms` / `dim_student_attendance_intervention_types`;
  `location_key` on `dim_work_assignment_locations` / `dim_terms`;
  `shared_with_location_key` on `fct_job_candidate_applications`; structural FKs
  approved earlier in the audit (student_key on
  dim_student_assessment_expectations; staff_key on fct_family_communications;
  referring_staff_key on fct_behavioral_incidents;
  time_service_supervisor_staff_key on dim_staff_work_assignments;
  manager_staff_key on dim_work_assignment_reporting_relationships;
  staff_observation_type_key and staff_observation_rubric_key on
  fct_staff_observations; family_communication_key on
  fct_student_attendance_interventions).
- **Group 2 — simple moves**: `aligned_academic_subject` /
  `combined_academic_subject` / `credit_category` on `dim_assessments` (moved
  from `fct_assessment_scores_student_scoped`); `district_student_identifier`
  and `salesforce_contact_id` on `dim_students`.
- **Group 3 — deferred to follow-up PRs**: `points_earned` +
  `numeric_grade_earned` split on `fct_grades_assignments` (requires staging
  changes); `address_line_one` / `address_line_two` / `city` / `postal_code` on
  `dim_locations` (requires address data to flow into the KIPP location master,
  not only ADP's work-location dim).

### Out of scope for this PR

- Tier 3 structural issues (#3640, #3641, #3646, #3648) — each requires
  domain-specific upstream decisions (crosswalks, seeds, intermediate
  restructures) that warrant independent review.
- Spec "Structural follow-ups" — `dim_colleges` KIPPADB sourcing refactor;
  `dim_student_contact_persons.email`/`phone` pivot bug;
  `dim_college_enrollments.degree_title` join issue; `dim_staff_status` empty
  table; region traversal cascade (`dim_regions.legal_entity` unpopulated,
  `dim_locations.region` mis-populated); `dim_assessments` `scope` vs
  `assessment_scope` untangling. All queued under #3631 umbrella.

## Execution plan

### Phase 1 — Upstream dedups

Two self-contained fixes, shipped as two commits.

1. **`#3637`: dedup `stg_people__employee_numbers`.** 91 rows have multiple
   `adp_associate_id` mappings per `employee_number`. Use
   `dbt_utils.deduplicate` partitioned by `employee_number`, ordering by
   active-then-recent. Add a `unique` test on `employee_number` to lock the
   invariant. Remove the `SELECT DISTINCT employee_number` + existing
   `TODO: #3637` comment in `dim_staff`. See Open Questions for the
   active-then-recent column ordering.
2. **`#3633`: dedup `int_people__location_crosswalk`.** The model produces
   duplicate rows per
   `(location_powerschool_school_id, location_dagster_code_location)`. Apply
   `dbt_utils.deduplicate` at that grain. Add a unique test on the composite.
   Remove `SELECT DISTINCT` workarounds in the eight downstream mart consumers
   listed in #3633: `dim_locations`, `dim_school_calendars`,
   `dim_student_enrollments`, `dim_course_sections`, `dim_assessment_targets`,
   `fct_student_attendance_daily`, `fct_student_attendance_interventions`,
   `fct_behavioral_incidents`.

Both dedups must pass their new uniqueness tests before Phase 2 begins. If the
dedup ordering cannot produce a single canonical row per key without data loss,
that's a blocker — surface it and stop.

### Phase 2 — Audit execution (mart layer)

One commit per domain. Fourteen commits total, following the domain order below.
Cross-cutting adds (e.g., `region_key` cascade) land with the first domain that
needs them and are referenced — not re-created — by later domains.

Per domain, per model: apply the inventory decisions to the mart `.sql` and its
properties `.yml` in lockstep:

- **Renames**: rename the column in the model SQL (source alias or CTE rename),
  update `name:` and `description:` in the YAML, and verify any `data_tests:`
  migrate with the column.
- **Removes**: strip from the final SELECT; strip the matching YAML column
  block; if the column was the only thing pulling a CTE, clean up the CTE too.
  For R9 removes whose FK exists already, verify the FK is correctly declared in
  YAML with `relationships` test to the parent dim.
- **Structural adds (Groups 1 + 2)**: add the new column to the SQL (derive from
  existing joins; no new upstream joins for Group 1 FKs if the parent dim's
  natural key is already in scope), and add the YAML column block with
  description and appropriate tests (`not_null` + `relationships` for FKs).

**Domain order**:

1. IT (`fct_support_tickets`) — validation-sized domain; 1 model.
2. Course — 2 models.
3. Staffing — 1 model.
4. Talent — 2 models.
5. Survey — 7 models but few per model.
6. College — 2 models.
7. Attendance — 4 models.
8. Conformed (`dim_locations`, `dim_regions`, `dim_terms`,
   `dim_school_calendars`) — cross-cutting; region_key cascade lands here.
9. Behavioral — 3 models.
10. Student — 4 models.
11. Gradebook — 3 models.
12. Observation — 6 models.
13. Assessment — 5 models.
14. Staff — 11 models; largest.

Rationale for sequence: IT first as smallest real-world validation. Conformed
early-middle because its FKs cascade into most later domains. Staff last because
it's the largest and most interconnected.

### Phase 3 — Verification and cleanup

One final commit for the cleanup sweep and documentation.

- `uv run dbt parse` + `uv run dbt compile` clean against the whole project.
- `dbt build --select state:modified+ --full-refresh` via dbt Cloud CI (staging
  target, defers to Staging environment per
  [`src/dbt/kipptaf/CLAUDE.md`](../../src/dbt/kipptaf/CLAUDE.md)).
- Exposure sweep: grep `models/exposures/` for any column names on the rename or
  remove lists; update matching Tableau/Google Sheets/extract exposures.
- Remove any remaining `SELECT DISTINCT` workaround CTEs freed by Phase 1 that
  weren't caught inside a per-domain commit.
- Update `docs/superpowers/specs/2026-04-15-column-naming-audit.md` "Hash-change
  posture" with the set of surrogate keys whose input composition changed
  (region-text → region_key; commlog_reason → family_communication_reason; etc.)
  so consumers have a precise before/after hash-change list.

## Hash-change posture

Per the audit spec, this refactor is prerelease and preserves no backward
compatibility. Expected hash-change surrogate keys (non-exhaustive; final list
goes into the Phase 3 cleanup commit):

- `dim_terms.term_key` — composition loses `region` text, gains `region_key`;
  loses `school_id`, gains `location_key`.
- `dim_regions.region_key` — unchanged (derived from `region` name string, which
  stays stable as `region_name` post-rename).
- `dim_student_attendance_intervention_types.intervention_type_key` —
  composition gains `region_key`, renamed input `commlog_reason` →
  `family_communication_reason` (value may change at the staging layer as well).
- Role-playing/derived keys in `fct_staff_observation_expectations` and
  `fct_grades_*` that include `term_*` composite fields.

## Open questions to resolve during implementation

- **#3637 canonical ordering**: which column defines "most recent active"? The
  issue suggests active + recent; confirm during staging rewrite.
- **#3633 canonical ordering**: the crosswalk duplicates have no obvious
  ordering — all fields match except the dup cause. Investigate upstream (likely
  an unintentional CROSS JOIN somewhere) and fix root cause rather than just
  adding deduplicate.
- **Exposure fan-out**: the exposure sweep may find references in
  `models/exposures/**` that require Tableau workbook edits outside this repo.
  Flag these as follow-up work; do not block the PR on them.

## Follow-up PRs

After this PR merges, the deferred work lands as separate PRs tracked against
their original issues:

- **#3640** — add `student_section_enrollment_key` FK to
  `dim_student_assessment_expectations` (requires `int_assessments__scaffold`
  rework).
- **#3641** — add `staff_observation_type_key` FK to
  `dim_staff_observation_expectations` (requires new crosswalk).
- **#3646** — create definition-grain catalog intermediates for
  `dim_assessments` / `dim_surveys` (addresses "scope vs assessment_scope"
  untangling flag).
- **#3648** — add `assessment_key` FK crosswalks for
  `dim_assessment_comparisons` / `dim_assessment_targets` (requires source
  crosswalk or seed).
- **#3631 umbrella** — Group 3 structural adds (`fct_grades_assignments`
  polymorphic score split; `dim_locations` address unification) plus all items
  in the audit spec's "Structural follow-ups" section.
