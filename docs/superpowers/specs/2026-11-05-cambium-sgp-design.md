# Cambium student growth percentile (SGP): design

Issue: [#6279](https://github.com/TEAMSchools/teamster/issues/6279). Size: a
small change.

## Intent

Cambium's NJSLA file carries `studentgrowthpercentile`, and the cambium package
drops it at staging. We want SGP on the crosswalked NJ state score rows so that
a follow-on Tableau tool can report school-level SGP.

## What the data holds

- Cambium fills SGP for ELA grades 4 to 8 (test codes `ELA04`–`ELA08`) and Math
  grades 4 to 7 (`MAT04`–`MAT07`). Every other test code is null, including
  `ELA03`, `ELA09`, `MAT08`, Science, `ALG01`, and `GEO01`.
- The source column is a STRING. Missing values are true nulls: no empty
  strings, no non-integer values. Populated values run 1 to 99.
- `src_cambium__njgpa` and `src_cambium__eoc` carry the column with 0 values.
  The Pearson files never had it, so SGP history starts with Spring 2026
  (`academic_year = 2025`).

## Goals

1. PR 1, cambium package: expose `student_growth_percentile` (int64) in
   `stg_cambium__njsla` and carry it through `int_cambium__all_assessments`.
2. PR 2, kipptaf: carry the column into `int_assessments__state_nj_scores`, the
   first model where the student crosswalk corrects `student_number`.

## Non-goals

- The `rpt_tableau__*` model and its workbook. A follow-on builds them under
  #6279 (see _Follow-on_ below).
- `int_assessments__state_scores`. SGP is NJ-only, so the column would need a
  Florida null pad across 11 consumers for no reader.
- `fct_assessment_scores_enrollment_scoped`, NJGPA, EOC, and Pearson years.

## Anti-goals

- A consumer that reads SGP before the crosswalk. `int_ignite__state_assessment`
  reads kipptaf `int_cambium__all_assessments` directly; it must not become the
  SGP source for reporting.
- A new column that breaks a contract-enforced consumer. Every current consumer
  of both changed models enumerates its columns; the plan re-checks this.

## Approaches

1. **Two PRs, package first (chosen).** The repo rule for a new package column
   that kipptaf reads (`.claude/rules/dbt-models.md`, "kipptaf source consumers
   of district columns"). PR 2 waits for the Dagster prod rebuild in Newark,
   Camden, and Paterson, then a refresh of the `zz_stg_*` copies.
2. **One PR.** Force the kipptaf union wrapper `state:modified` and build the
   package model into the shared `zz_stg_*` datasets. Rejected: it needs
   authorized shared staging writes and buys nothing while the report is a
   follow-on.
3. **Fold the kipptaf change into the report follow-on.** Rejected: SGP would
   have no crosswalked home until the report ships, and the report PR would
   inherit the cross-project wait.

## Design

PR 1, `src/dbt/cambium/`:

- `stg_cambium__njsla.sql`: add the line below next to the sibling casts.

  ```sql
  cast(studentgrowthpercentile as int) as student_growth_percentile,
  ```

  Plain `cast`, matching the siblings: the data has no value `safe_cast` would
  rescue, and a future bad value should fail loudly.

- `stg_cambium__njsla.yml`: the column with `data_type: int64`, a description,
  and `config.meta.contains_pii: true` (a student-level score). A range test of
  1 to 99 (my call).
- `int_cambium__all_assessments.sql` (contract-enforced): the column in
  `njsla_aligned`, `cast(null as int64)` in `njgpa_aligned`, the `aligned` loop,
  and the final select. Same column in its yml.
- The kipptaf `stg_cambium__njsla` and `int_cambium__all_assessments` are
  `union_relations` passthroughs and need no edit.
- Verify with local dev builds in all 3 districts. The non-null count per test
  code must reconcile with the source after the staging filters
  (`summative_flag = 'Y'`, `test_attemptedness_flag = 'Y'`, dedupe on
  `student_test_uuid`) and the package int model's `test_status = 'completed'`.

PR 2,
`src/dbt/kipptaf/models/assessments/intermediate/int_assessments__state_nj_scores.sql`:

- The column in the Cambium branch of `unioned`, `cast(null as int64)` in the
  Pearson branch, and `u.student_growth_percentile` in the final select. The
  crosswalk join replaces only `student_number`, so SGP stays on its
  `student_test_uuid` row.

Both PRs say `Refs #6279`. The branch is not linked to the issue, so merging a
PR leaves #6279 open for the follow-on.

## Follow-on: the Tableau tool

Settled with the requester:

- School-level SGP: the median per school and the distribution of students
  across levels.
- A new Tableau tool, separate from the State Testing Analysis Tool (STAT).
- No expectation that the figures match the median SGP (mSGP) that NJDOE
  publishes. The tool should say "KIPP-calculated" so that nobody files the
  difference as a bug.

Proposed, not yet confirmed:

- Campus is the school where the student tested, from PowerSchool, because the
  state file carries no KIPP campus.
- The tool shows only test codes that carry SGP.

Open:

- What "level" means: growth level (low 1–34, typical 35–65, high 66–99; confirm
  the cutoffs), NJSLA performance level, or school level. Carrying all 3 on each
  row costs little.
- Whether the `rpt_` reads `int_assessments__state_nj_scores` or the mart.
  Architecture rule A2 prefers the mart. Two arguments against the mart:
  `fct_assessment_scores_enrollment_scoped` inner-joins resolved section
  enrollments, which drops students, and it carries no state-file student group
  fields. The no-match decision weakens the first argument.
