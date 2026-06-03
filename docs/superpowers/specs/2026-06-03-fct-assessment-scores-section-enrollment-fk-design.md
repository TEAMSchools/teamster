# Design: `student_section_enrollment_key` on `fct_assessment_scores_enrollment_scoped`

- **Issue:** [#4089](https://github.com/TEAMSchools/teamster/issues/4089)
- **Date:** 2026-06-03
- **Status:** Approved — ready for implementation plan

## Background

`fct_assessment_scores_enrollment_scoped` exposes `student_key`,
`assessment_administration_key`, and `test_date_key`. It has no direct link to
`dim_student_section_enrollments`, so the fact cannot be joined to the
section/course/teacher context, and cannot be matched per-student to
`bridge_assessment_expectations_enrollment_scoped` for completion analysis.

The two existing routes both fail:

- **fact → administration → bridge → enrollment:**
  `assessment_administration_key` is not student-specific (one administration
  maps to ~255 section enrollments), and the bridge carries no student column,
  so the join fans out across every student in the administration.
- **fact → student → enrollments:** student-correct but subject-blind — a
  student has many section enrollments and nothing selects the one matching the
  assessment's subject.

The correct section is the _intersection_ of "this student's" and "expected for
this administration's subject" — a two-coordinate resolution no single FK
traversal can express. That intersection is computed upstream in
`int_assessments__scaffold` (matched on subject_area + region + enrollment-date
window). Materializing it onto the fact is the fix.

## Goal and scope

Add a nullable FK `student_section_enrollment_key` →
`dim_student_section_enrollments` to the fact.

Interim canonical-grain solution. The atomic (member-grain) alternative and the
Kimball denormalization lever are tracked in
[#4107](https://github.com/TEAMSchools/teamster/issues/4107).

### Coverage

Populated **only** for internal, non-replacement rows with a resolvable section
enrollment — the exact scope of
`bridge_assessment_expectations_enrollment_scoped`
(`is_internal_assessment AND NOT is_replacement AND cc_dcid IS NOT NULL AND cc_source_project IS NOT NULL`).
NULL for:

- state assessments (NJSLA, NJGPA, FAST) — no PowerSchool course enrollment
- replacement curriculum — no enrollment by definition
- ES Writing K-4 Newark/Camden — no course-enrollment row
- internal rows whose section did not resolve

`student_key` remains the universal student link (covers 100% of rows);
`student_section_enrollment_key` is additive context for the resolvable subset.
This mirrors the domain's two-bridge split — `*_enrollment_scoped` (has an
enrollment, no `student_key`) vs `*_student_scoped` (no enrollment, carries
`student_key`).

## Resolver (dedicated intermediate model)

A new model `int_assessments__resolved_section_enrollments` resolves one section
enrollment per `(student, canonical assessment, source)` for internal scored
assessments. Extracting it (rather than a CTE in the fact) keeps the tiebreak
logic in a single-purpose, independently unit-testable model with its own grain
invariant — see _Tests_.

- **Source:** `int_assessments__scaffold`, filtered to the coverage scope above
  (identical to the enrollment bridge → guarantees the picked section is one of
  the bridge's expectation enrollments, preserving fact↔bridge conformance).
- **Join `int_assessments__assessments_canonical`** on `canonical_assessment_id`
  to obtain `canonical_administered_date` (same re-join the bridge uses).
- **Anchor date:**
  `coalesce(min(date_taken) per (student, canonical, source), canonical_administered_date)`
  — the actual sitting date when present, else the scheduled administration
  date.
- **Pick rule** (via `dbt_utils.deduplicate`, ordered
  `is_anchor_in_window desc, cc_dateleft desc`):
  1. exactly one candidate `cc_dcid` → use it (anchor irrelevant);
  2. multiple candidates → the one whose `[cc_dateenrolled, cc_dateleft]` window
     contains the anchor;
  3. still tied → latest `cc_dateleft`.
- **Grain / output:** one row per
  `(powerschool_student_number, canonical_assessment_id, _dbt_source_project)`;
  emits those keys plus `cc_dcid`, `cc_source_project`, and the computed
  `student_section_enrollment_key`. Hash composition is **identical to
  `dim_student_section_enrollments` and the enrollment bridge** — `cc_dcid` +
  `cc_source_project` (the course-enrollment source project, **not** the
  region-derived `_dbt_source_project`).

The pick rule self-cleans the dominant ambiguity source: ~0.5% of
`(student, canonical)` pairs map to multiple sections, and ~71% of those are
cross-year [#3801](https://github.com/TEAMSchools/teamster/issues/3801) phantoms
(a duplicated member assessment mis-tagged into another academic year). Those
phantom enrollments' windows do not contain the real anchor date, so they are
excluded by construction.

## Wiring into the fact

The **internal branch** LEFT JOINs
`int_assessments__resolved_section_enrollments` on
`(student_number, canonical_assessment_id, _dbt_source_project)` and selects its
`student_section_enrollment_key` directly — the LEFT-JOIN miss yields NULL for
unresolved rows, so no `if(...)` wrap is needed in the fact (the hash and its
nullability are owned by the intermediate). The **state branch** selects
`cast(null as string) as student_section_enrollment_key`.

## Additive upstream edit

`int_assessments__scaffold` computes `cc_dateenrolled` / `cc_dateleft` in its
internal CTE but does not project them. Surface both in the final SELECT (the
three non-enrollment union branches emit `cast(null as date)`). Additive-only —
safe for the scaffold's other consumers (the two bridges, `response_rollup`,
tests, one extract).

## Grain safety and diamond analysis

- **Grain:** the intermediate is unique on its join key (enforced by its own
  `unique_combination_of_columns` test), so the LEFT JOIN cannot fan the fact.
  The existing `assessment_score_key` unique test is the backstop; validate
  populated/null counts in the PR-branch schema after build.
- **Direct FKs — no diamond:** `student_key`, `assessment_administration_key`,
  `test_date_key`, and the new `student_section_enrollment_key` point at four
  distinct dims, none reachable from another. `dim_student_section_enrollments`
  is genuinely new context, not an FK shortcut to an already-reachable dim. No
  deep-dim attributes are denormalized onto the row.
- **Latent transitive overlap (Cube constraint):**
  `student_section_enrollment_key → dim_student_section_enrollments → student_enrollment_key → dim_student_enrollments → student_key → dim_students`
  overlaps the direct `student_key → dim_students`. This is inherent to any
  section/enrollment FK on a student-keyed fact (cf. `fct_grades_term`). It is
  never exercised — the section FK exists for section/course/teacher/term
  context; the student is already reached via `student_key`. **Constraint for
  the Cube follow-up:** join `dim_students` via `student_key` only; declare the
  `student_section_enrollment_key` path for section/course/teacher/term context,
  leaving the enrollment→student edge degenerate (per `src/cube/CLAUDE.md`).
- Pre-existing internal diamonds _under_ `dim_student_section_enrollments` (two
  paths to `dim_locations`; date FKs to `dim_dates`) are not introduced here and
  are likewise Cube-join concerns.

## Tests and YAML

- **Intermediate** (`int_assessments__resolved_section_enrollments`):
  `dbt_utils.unique_combination_of_columns` on
  `(powerschool_student_number, canonical_assessment_id, _dbt_source_project)`
  (the grain invariant), plus a **dbt unit test** locking the tiebreak —
  scenarios: single candidate (resolves regardless of window), multiple
  candidates with one in-window (the #3801 phantom-exclusion case), multiple
  candidates none in-window (falls back to latest `cc_dateleft`), and null
  `date_taken` (anchor falls back to the administration date). This is the
  repo's first dbt unit test; it gates materialization and is the deterministic
  regression guard the prod-data validation queries can't promise.
- **Fact** (`properties/fct_assessment_scores_enrollment_scoped.yml`): new
  column with source-agnostic `description`, `foreign_key` constraint
  (`warn_unsupported: false`) to `dim_student_section_enrollments`, and a
  nullable `relationships` test (no `not_null` — the FK is nullable). Update the
  model `description` to note the new FK.
- No #3801 warn test in scope — #3801 monitoring stays where it lives.

## Hash discipline

New column only; no existing surrogate-key composition changes → zero downstream
hash churn. This is a "structural add" (new FK where none existed) per the marts
hash-change rules.

## Out of scope

- **Cube follow-up** (cube `sql:` SELECT, bridge join fix, section/teacher
  dims): gated on this column landing + materializing, and on cristinabaldor's
  Cube branch. Carries the diamond constraint above.
- **Atomic-grain assessment fact + metrics-layer rollup:**
  [#4107](https://github.com/TEAMSchools/teamster/issues/4107).

## Rejected alternatives

- **Resolve via `int_assessments__response_rollup` (Option B):** its existing
  `tiebroken_attrs` window orders by _earliest_ `date_taken` (a #3801 location
  workaround slated for removal) — wrong selection rule, would pick the phantom
  section, couples a permanent FK to a temporary workaround, and rides along to
  ~10 unrelated consumers.
- **Resolver as a CTE inside the fact:** keeps the change to one file, but the
  tiebreak logic can only be unit-tested _through_ the fact (mocking ~4
  populated inputs with consistent join keys), and the grain invariant has no
  home of its own. Rejected in favor of the dedicated intermediate once a unit
  test entered scope — testability and a self-contained grain test outweigh the
  smaller footprint.
- **Drop `student_key`, reach student via the enrollment chain:** orphans every
  row without a section enrollment (all state assessments, replacement, ES
  Writing) from the student dimension. Non-starter.
- **Atomic member-grain fact + metrics-layer rollup:** eliminates the tiebreak
  but blocked — Cube cannot assign performance bands (a data-driven range lookup
  on an aggregated value). Tracked in #4107.
