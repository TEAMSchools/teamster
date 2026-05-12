# ES Writing bridge coverage — design

Refs #3777. Part of project [#4](https://github.com/orgs/TEAMSchools/projects/4)
"enrollment FK cluster" batch.

## Problem

ES Writing (grades K-4 in Newark and Camden) assessment expectations don't
appear in either bridge linking student section enrollments to scheduled
assessment administrations. The expectations exist in
`int_assessments__scaffold` but are filtered out of both bridges, so the network
can't slice ES Writing administrations by student/section in the dimensional
model.

Current scaffold sizing (BigQuery, 2026-05-12):

- 116,776 internal-assessment, non-replacement rows with `cc_dcid IS NULL` — the
  ES Writing class.
- 1,856 replacement-assessment rows with `cc_dcid IS NULL` — fully contained
  inside the NULL-cc_dcid set. These already flow into
  `bridge_assessment_expectations_student_scoped` via the `is_replacement`
  filter.
- 0 internal-assessment rows with `cc_dcid IS NULL` and a null
  `powerschool_student_number` — every ES Writing row has a resolvable student.

## Root cause

`int_assessments__course_enrollments` builds the ES Writing branch (lines 41-64)
from `base_powerschool__student_enrollments` (student-grain), hardcoding
`cc_dcid = NULL` and `_dbt_source_relation = NULL` because no underlying
course-section enrollment row exists. The `base_powerschool__course_enrollments`
source has no ES Writing equivalent.

`bridge_assessment_expectations_enrollment_scoped` filters
`WHERE cc_dcid IS NOT NULL AND cc_source_relation IS NOT NULL` (lines 28-32).
The model comment correctly notes that allowing NULL inputs would collide on the
placeholder hash of `student_section_enrollment_key`.

`bridge_assessment_expectations_student_scoped` filters `WHERE is_replacement`
(line 31). All current student-scoped rows have NULL `cc_dcid` — the bridge is
already the "no section context" path, just currently constrained to one of two
cases (replacement). ES Writing is the second case and is excluded.

## Decision

**Widen the `bridge_assessment_expectations_student_scoped` filter to admit
every internal-assessment row that the enrollment-scoped bridge cannot
represent.** Concretely: replacements OR ES Writing (i.e. any internal row with
NULL section context). Do not synthesize a fake `cc_dcid`, do not add a third
bridge.

Rejected alternatives:

- _Synthesize a deterministic `cc_dcid` from the student enrollment row_ —
  manufactures a section relationship that doesn't exist; downstream consumers
  traversing `dim_student_section_enrollments → dim_sections` would treat it as
  real. Also requires the same synthesis in `dim_student_section_enrollments`,
  expanding scope.
- _Add a third bridge
  `bridge_assessment_expectations_enrollment_scoped__no_section`_ — unnecessary;
  the student-scoped bridge already encodes the "no-section-context" grain. The
  current `is_replacement` filter is a coincidence of historical rollout, not a
  semantic boundary.
- _Drop the `cc_dcid IS NOT NULL` filter on the enrollment-scoped bridge_ — the
  PK would collapse for NULL-cc_dcid rows (placeholder hash collision), failing
  the uniqueness test. Even with a fallback discriminator, the resulting
  `student_section_enrollment_key` would not link to anything in
  `dim_student_section_enrollments`.

## Implementation

### `bridge_assessment_expectations_student_scoped.sql`

Replace the `WHERE` clause (line 31):

```sql
where
    sc.is_internal_assessment
    and (sc.is_replacement or sc.cc_dcid is null)
    and sc.powerschool_student_number is not null
```

`is_internal_assessment` is added explicitly to mirror the producer side and
prevent external assessments (which also have `cc_dcid IS NULL`) from leaking
in. Confirmed against current scaffold:

- Internal + non-replacement + NULL cc_dcid: 116,776 (ES Writing)
- Internal + replacement: 1,856 (already covered today)
- External + NULL cc_dcid: 1.6M rows — must stay excluded

Row count change: +114,920 net rows in
`bridge_assessment_expectations_student_scoped` (116,776 ES Writing minus the
1,856 replacement rows already counted). No grain change.

### `bridge_assessment_expectations_enrollment_scoped.sql`

No SQL change. Update the inline comment (lines 23-27) to point at the
student-scoped bridge as the home for NULL-cc_dcid rows rather than implying
they have no representation.

### YAML

- `bridge_assessment_expectations_student_scoped` model description: state that
  the bridge carries internal assessment expectations that cannot be attributed
  to a student section enrollment — replacements and ES Writing.
- `bridge_assessment_expectations_enrollment_scoped` model description: state
  that it only covers expectations with a resolvable section enrollment; ES
  Writing and replacements live in the student-scoped bridge.
- Tests: existing PK uniqueness on `assessment_expectation_key` continues to
  hold — composition unchanged. Relationships test
  `bridge_assessment_expectations_student_scoped.assessment_administration_key → dim_assessment_administrations`
  must still pass after widening; verify in PR-branch CI.

## Out of scope

- **#3794** (survey responses FK gap) — separate spec, separate PR; same
  PR-batch label on project board.
- **#3817** (regions_assessed tagging) — moved off project 4; ops follow-up
  only.
- **`int_assessments__course_enrollments` ES Writing branch refactor** — no
  change. The NULL `cc_dcid` is the truthful representation of "no section
  enrollment exists." Synthesizing a value would propagate fiction downstream.
- **`dim_student_section_enrollments` ES Writing coverage** — out of scope. ES
  Writing intentionally has no section enrollment to dimensionalize.

## Pre-merge checklist (per `marts/CLAUDE.md`)

- [ ] Scan touched models for diamond paths (none introduced — only widens an
      existing WHERE filter).
- [ ] Scan touched models for R1–R10 violations (no new columns; existing
      `cc_dcid`/`cc_source_relation` references are upstream-only and not
      exposed in mart SELECTs).
- [ ] Pull marts-model warnings from latest CI run via dbt MCP
      `get_job_run_error(warning_only=true)`; confirm no new bridge warnings
      surface for the widened row set (FK to `dim_assessment_administrations`,
      FK to `dim_students`).
- [ ] Scan
      [project board #4](https://github.com/orgs/TEAMSchools/projects/4/views/1)
      for bonus issues incidentally resolved; close them in the PR.
- [ ] Confirm `bridge_assessment_expectations_student_scoped` PK uniqueness test
      passes on the PR-branch schema with the expanded row set.

## Acceptance criteria

- `bridge_assessment_expectations_student_scoped` row count increases by
  approximately +114,920 (the ES Writing class), with no fan-out.
- All ES Writing administrations now appear in
  `bridge_assessment_expectations_student_scoped`. Verify via:

  ```sql
  select count(*) as n_es_writing_admins_in_bridge
  from `teamster-332318.kipptaf_marts.bridge_assessment_expectations_student_scoped` b
  inner join `teamster-332318.kipptaf_assessments.int_assessments__scaffold` sc
      using (assessment_id)
  where sc.is_internal_assessment
      and not sc.is_replacement
      and sc.cc_dcid is null
  ```

  Expected ≈ 116,776.

- `bridge_assessment_expectations_enrollment_scoped` row count unchanged.
- PK uniqueness on both bridges still passes.
- No new failing or warning relationships tests on either bridge.
