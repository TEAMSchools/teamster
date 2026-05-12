# ES Writing bridge coverage — design

Refs #3777. Part of project [#4](https://github.com/orgs/TEAMSchools/projects/4)
"enrollment FK cluster" batch. Ships a scoped slice of #3142
(`_dbt_source_project` promotion on two union models) and #3820 (region-prefix
hash on `student_section_enrollment_key`) as the additive upstream edits this
fix requires.

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

### Secondary defect (discovered while drafting)

`int_assessments__course_enrollments.sql` lines 67-72 dedupes on
`(powerschool_student_number, illuminate_academic_year, illuminate_subject_area, cc_dateenrolled)`
with no source-region discriminator. PowerSchool `student_number` values are
district-scoped; a Newark student #1234 and a Camden student #1234 doing ES
Writing in the same AY/subject_area/enrollment date would silently collapse to
one row. The K-8/HS branches dodge this via `cc_dcid` (globally distinct within
the partition), but the ES Writing branch's all-NULL plumbing leaves the
partition blind.

### Tertiary defect (discovered while drafting)

The K-8/HS branches inherit `_dbt_source_relation` from
`base_powerschool__course_enrollments` (suffix
`..._base_powerschool__course_enrollments`). If the ES Writing branch were fixed
by carrying `co._dbt_source_relation` from
`base_powerschool__student_enrollments`, its rows would carry suffix
`..._base_powerschool__student_enrollments` instead. Same district, different
table-name suffix — the value is no longer a region-only identifier. This is
exactly the fragility #3820 documents, and the column-promotion pattern from
#3142 is the canonical fix.

## Decision

Three changes, ordered upstream → downstream:

1. **(Scoped #3142)** Promote `_dbt_source_project` as a materialized column on
   the two base union models this PR touches:
   `base_powerschool__course_enrollments` and
   `base_powerschool__student_enrollments`. Value:
   `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` — the same logic
   `extract_code_location()` already uses.
2. **(Scoped #3820)** Recompose `student_section_enrollment_key` on both the
   producer (`dim_student_section_enrollments`) and the consumer
   (`bridge_assessment_expectations_enrollment_scoped`) to hash
   `(cc_dcid, _dbt_source_project)` instead of
   `(cc_dcid, _dbt_source_relation)`. Region-only suffix is consistent across
   all upstream union tables and removes the cross-source-relation fragility.
3. **(#3777 core)** Widen the `bridge_assessment_expectations_student_scoped`
   filter to admit every internal-assessment row that the enrollment-scoped
   bridge cannot represent: replacements OR ES Writing (i.e. any internal row
   with NULL section context).

Rejected alternatives:

- _Synthesize a deterministic `cc_dcid` from the student enrollment row_ —
  manufactures a section relationship that doesn't exist; downstream consumers
  traversing `dim_student_section_enrollments → dim_sections` would treat it as
  real.
- _Add a third bridge
  `bridge_assessment_expectations_enrollment_scoped__no_section`_ — unnecessary;
  the student-scoped bridge already encodes the "no-section-context" grain. The
  current `is_replacement` filter is a coincidence of historical rollout.
- _Drop the `cc_dcid IS NOT NULL` filter on the enrollment-scoped bridge_ — the
  PK would collapse for NULL-cc_dcid rows (placeholder hash collision), failing
  the uniqueness test.
- _Use `_dbt_source_relation` (not `_dbt_source_project`) as the ES Writing
  discriminator_ — fixes the dedup collision but propagates the table-name
  asymmetry that #3820 calls out; cleaner to do the column-promotion now.
- _Ship the full #3142 (all 73 union models) in this PR_ — out of scope;
  marts/CLAUDE.md permits the additive upstream edit only for the models this
  PR's join/hash changes touch.

## Implementation

### `base_powerschool__course_enrollments` (additive upstream)

Add a materialized `_dbt_source_project` column. The model is a
`dbt_utils.union_relations` view; add the column to the post-union SELECT:

```sql
select
    *,
    regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,
from {{ dbt_utils.union_relations(...) }}
```

Apply the same change to `base_powerschool__student_enrollments`. Both base
models are intermediate-tier (`contract: enforced: false` per `dbt_project.yml`
defaults), so no properties YAML column entry is required; add to descriptions
only if a properties YAML already exists for the model.

The remaining 71 union models touched by full #3142 are out of scope; the new
column lives alongside `_dbt_source_relation` until #3142 ships and the macro
`extract_code_location` is renamed / retired. Reference `_dbt_source_project`
explicitly in dependent SELECTs rather than `SELECT *` to make the dependency
visible.

### `int_assessments__course_enrollments.sql`

- K-12 branch (lines 4-36): add `ce._dbt_source_project` to the SELECT.
- ES Writing branch (lines 40-64): replace
  `cast(null as string) as _dbt_source_relation` with `co._dbt_source_project`.
  Leave `cc_dcid = NULL` — there is genuinely no course-enrollment row to
  attribute. (Leave `_dbt_source_relation` NULL too — only `_dbt_source_project`
  is reliable across the two source tables.)
- Trailing dedup (lines 67-72): add `_dbt_source_project` to `partition_by`.
  Closes the cross-district student-number collision risk.

### `int_assessments__scaffold.sql`

- K-8 internal branch (lines 74) and HS internal branch (line 124): replace
  `ce._dbt_source_relation as cc_source_relation` with
  `ce._dbt_source_project as cc_source_project`.
- Replacement branch (line 213) and external branch (line 271): replace
  `cast(null as string) as cc_source_relation` with
  `cast(null as string) as cc_source_project`. (These branches have no
  enrollment context.)
- Final SELECT and properties YAML: rename `cc_source_relation` →
  `cc_source_project`. Update `config.meta.source_column` accordingly.

### `bridge_assessment_expectations_enrollment_scoped.sql`

- Rename SELECT reference and hash input from `cc_source_relation` to
  `cc_source_project`.
- WHERE clause: `cc_source_relation IS NOT NULL` →
  `cc_source_project IS NOT NULL`. (Combined with `cc_dcid IS NOT NULL`, ES
  Writing rows are still excluded.)
- Inline comment (lines 23-27): update to reference the student-scoped bridge as
  the home for NULL-cc_dcid rows.

### `bridge_assessment_expectations_student_scoped.sql`

Replace the `WHERE` clause (line 31):

```sql
where
    sc.is_internal_assessment
    and (sc.is_replacement or sc.cc_dcid is null)
    and sc.powerschool_student_number is not null
```

`is_internal_assessment` is added explicitly to keep external assessments (which
also have `cc_dcid IS NULL`) out of the bridge. Confirmed against current
scaffold:

- Internal + non-replacement + NULL cc_dcid: 116,776 (ES Writing)
- Internal + replacement: 1,856 (already covered today, all internal)
- External + NULL cc_dcid: 1.6M rows — must stay excluded

Row count change: +114,920 net rows. No grain change.

### `dim_student_section_enrollments.sql`

Swap `student_section_enrollment_key` hash composition (line 74):

```sql
{{ dbt_utils.generate_surrogate_key(["cc_dcid", "_dbt_source_project"]) }}
    as student_section_enrollment_key,
```

The `replace()` workaround on `course_section_key` (lines 79-93) stays — that's
`course_section_key`'s alignment problem (dim_course_sections built from
`base_powerschool__sections`), and ships under #3820's full sweep, not here.
Update the TODO comment to flag that `student_section_enrollment_key` has been
migrated to `_dbt_source_project` and the remaining keys await #3820.

### YAML updates

- `bridge_assessment_expectations_student_scoped`: description states the bridge
  carries internal assessment expectations that cannot be attributed to a
  student section enrollment — replacements and ES Writing.
- `bridge_assessment_expectations_enrollment_scoped`: description states it only
  covers expectations with a resolvable section enrollment; ES Writing and
  replacements live in the student-scoped bridge.
- `int_assessments__scaffold`: rename `cc_source_relation` column entry to
  `cc_source_project`; update `source_column`.
- `int_assessments__course_enrollments`: add `_dbt_source_project` column entry;
  describe as the region prefix extracted from `_dbt_source_relation`.
- `base_powerschool__course_enrollments` and
  `base_powerschool__student_enrollments`: add `_dbt_source_project` column to
  any existing properties YAML; if no properties YAML exists, skip.

### Tests

- Existing PK uniqueness on both bridges continues to hold —
  `assessment_expectation_key` composition unchanged.
- `dim_student_section_enrollments` PK uniqueness
  (`student_section_enrollment_key`) — verify on PR-branch CI. Hash composition
  changed from `(cc_dcid, _dbt_source_relation)` to
  `(cc_dcid, _dbt_source_project)`; collision risk in theory only if two
  source-relations produce the same `cc_dcid` within the same region (not
  observed; PS `dcid` is globally unique within a district).
- `bridge_assessment_expectations_enrollment_scoped.student_section_enrollment_key → dim_student_section_enrollments.student_section_enrollment_key`
  relationships test must still pass after both sides swap to
  `_dbt_source_project`. Verify on PR-branch CI.
- Relationships test
  `bridge_assessment_expectations_student_scoped.assessment_administration_key → dim_assessment_administrations`
  continues to pass with the expanded row set.

## Out of scope

- **#3142** full implementation (71 remaining union models, macro rename, 268
  `union_dataset_join_clause` replacements, macro retirement) — this PR ships
  the column on 2 of 73 union models, scoped to the join/hash composition we're
  touching.
- **#3820** other affected files — `dim_courses.sql`, `dim_course_sections.sql`,
  and the `course_section_key` `replace()` hack on
  `dim_student_section_enrollments`. This PR migrates only
  `student_section_enrollment_key`.
- **#3794** (survey responses FK gap) — separate spec, separate PR; same
  PR-batch label.
- **#3817** (regions_assessed tagging) — off project 4; ops follow-up.
- **`dim_student_section_enrollments` ES Writing coverage** — ES Writing
  intentionally has no section enrollment to dimensionalize; the student-scoped
  bridge is the correct home.

## Pre-merge checklist (per `marts/CLAUDE.md`)

- [ ] Scan touched models for diamond paths (none introduced).
- [ ] Scan touched models for R1–R10 violations. `_dbt_source_project` and
      `cc_source_project` are plumbing — kept in intermediate layers, never
      surfaced in a mart SELECT (R8).
- [ ] Pull marts-model warnings from latest CI run via dbt MCP
      `get_job_run_error(warning_only=true)`; confirm no new bridge or dim
      warnings surface (FK to `dim_assessment_administrations`, FK to
      `dim_students`, `student_section_enrollment_key` uniqueness).
- [ ] Scan
      [project board #4](https://github.com/orgs/TEAMSchools/projects/4/views/1)
      for bonus issues incidentally resolved; close them in the PR (#3777
      closes; partial progress on #3142 / #3820 documented but they stay open).
- [ ] Confirm `bridge_assessment_expectations_student_scoped` PK uniqueness
      passes on PR-branch schema with the expanded row set.
- [ ] Confirm `dim_student_section_enrollments.student_section_enrollment_key`
      uniqueness passes with the swapped hash composition.
- [ ] Confirm
      `bridge_assessment_expectations_enrollment_scoped → dim_student_section_enrollments`
      relationships test passes (both sides now hash on `_dbt_source_project`).

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
- `dim_student_section_enrollments` row count unchanged; PK uniqueness still
  passes.
- `bridge_assessment_expectations_enrollment_scoped.student_section_enrollment_key → dim_student_section_enrollments.student_section_enrollment_key`
  relationships test orphan count unchanged from current prod (no new drift
  introduced by the hash swap).
- `int_assessments__course_enrollments` row count: verify no rows lost through
  the addition of `_dbt_source_project` to the dedup partition (any net change
  should be an _increase_ — previously-collapsed cross-district duplicates now
  preserved).
- PK uniqueness on `int_assessments__course_enrollments` still passes with the
  widened partition.
