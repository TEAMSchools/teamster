# mCLASS uniqueness: warn, defend, error

Refs #6385

## Why

Amplify filed results for 2 Paterson children under 1 student ID, and filed a
second same-day benchmark sitting under another ID. The mCLASS staging
uniqueness tests are `error`, and the SFTP export is one network-wide file, so
these few rows block DIBELS updates for every region. The mCLASS tests also do
not follow the repo's warn-defend-error rule (`.claude/rules/dbt-yaml.md`).

## Goals

- A misfiled Amplify row warns at staging and stops blocking the refresh.
- kipptaf drops the misfiled rows before they fan out downstream.
- Error tests prove the defense holds.

Non-goal: fixing the misfiled results. Amplify or the school moves them to the
right student in mCLASS.

## Approaches

- **A. Add the assessed grade to the mart key** in
  `fct_assessment_scores_enrollment_scoped`. Changes the key hash for every
  vendor row, so Cube consumers need checking. Rejected.
- **B. Drop same-day sittings at the source `int_`** (picked). A student sitting
  2 benchmark grades on 1 day is never legitimate (confirmed by the user), so
  dropping those rows loses no real data and the mart key stays unchanged.

## Design

1. **Warn.** In the `amplify` package, set the uniqueness tests on
   `stg_amplify__mclass__sftp__benchmark_student_summary` and
   `stg_amplify__mclass__sftp__pm_student_summary` to `severity: warn`. Each
   description names the defect (2 children's results filed under 1 ID) and the
   fix (move the result to the right student in mCLASS).
2. **Defend.** In the kipptaf source `int_` models, drop every row that collides
   with another row from the same source relation (`_dbt_source_relation_2`):
   - `int_amplify__mclass__benchmark_student_summary`: collisions on student,
     school year, and benchmark period, plus either the same assessment grade or
     the same device date.
   - `int_amplify__mclass__pm_student_summary`: collisions on the staging PM
     uniqueness key.
   - Collisions are counted within 1 source relation, so a row arriving through
     both the network file and the kipppaterson archive still fails downstream
     at error.
   - All colliding rows are dropped, not one picked: neither row can be trusted.
3. **Error proof.**
   - Add a uniqueness test at `error` on
     `int_amplify__mclass__benchmark_student_summary`, plus a same-day test at
     `error`.
   - Set `severity: error` on the
     `int_amplify__mclass__benchmark_student_summary_unpivot` uniqueness test.
   - Leave the aimline, PM intermediate, and mart tests at `error`.
4. **Docs.** Update `docs/models/dibels-dashboard-data-model.md` and the
   `dibels-dashboard` skill with the drop rule.

## Constraints

- The drop rule changes reported counts: a dropped student shows as Not Tested
  until Amplify moves the results. Teaching and Learning confirms the rule.
- Dedup stays in the source `int_` (A5).

## Left to the builder

- Whether a dbt unit test can mock refs feeding `union_relations`. If not, the
  proof is a warehouse check against prod data.
- Exact CTE shape of the collision count.
