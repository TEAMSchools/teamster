# NJ 504 flag from the PowerSchool state field: design

Issue: #6354. Related: #6284 (504 dimension and Cube field built on `is_504`),
#6350 (EdPlan 504 report ingestion).

## Why

The network 504 flag, `is_504` in kipptaf `int_students__student_enrollments`,
reads two different PowerSchool fields for New Jersey. Past enrollments read the
state field `S_NJ_REN_X.PID_504_TF`. The current school year reads the KIPP
custom field `U_STUDENTSUSERFIELDS.C_504_STATUS`.

Every PowerSchool state extract that carries 504 reads `PID_504_TF`: the Cambium
TIDE student file, the NJ SLA and SLA-S registration reports, and the NJ State
Assessment Registration Report sent to NJ SMART. No state report reads
`C_504_STATUS`, and Paterson's PowerSchool does not have it. So Paterson shows 0
students with a 504 this year, and the NJ State Test Roster and State Testing
Accommodations Tracker show a different 504 field than the one sent to the
state.

## Goals

1. For Newark, Camden, and Paterson, `is_504` reads `PID_504_TF` in every school
   year: `S_NJ_REN_X` for rows from a past-enrollment record, `S_NJ_STU_X` for
   every other row.
2. Schools get a one-time worklist of currently enrolled students whose flag
   changes or whose PowerSchool and EdPlan records disagree, so they can correct
   PowerSchool.

## Non-goals

- Retiring `C_504_STATUS` from the district staging models.
- Miami. Its branch keeps reading Focus `custom_621`.
- Loading EdPlan's 504 report (#6350), or making EdPlan the 504 source.
- A recurring discrepancy check.

## Anti-goals

- Any change to Miami's `is_504` values.
- Student-level data in the repo, a commit, a PR, or an issue comment.
- Breaking the kipptaf union of the 3 districts' `stg_powerschool__s_nj_stu_x`
  while the districts rebuild at different times.

## Constraints

- kipptaf reads `stg_powerschool__s_nj_stu_x` through an uncontracted
  `dbt_utils.union_relations` view over the 3 district sources. A column that
  some districts lack null-fills. A column whose type differs across districts
  fails the union.
- A value derived from one source column belongs in the staging model that reads
  it (`.claude/rules/dbt-sql.md`, S9).
- A district column that kipptaf reads through `source()` ships in two PRs, with
  a prod rebuild between them (`.claude/rules/dbt-models.md`).
- `int_students__student_enrollments` feeds most of kipptaf, so a change to it
  rebuilds a large graph in dbt Cloud CI.

## Approaches

| Choice                               | Options considered                                                                                   | Picked                   | Why                                                                                              |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------ |
| Rollout                              | Two PRs; one PR with seeded `zz_stg` copies; one PR comparing `njs.pid_504_tf = 1` inline in kipptaf | Two PRs (user)           | No shared staging writes, and keeps the derivation in staging (S9).                              |
| Column shape                         | New boolean `is_504`; retype `pid_504_tf` to boolean like `stg_powerschool__s_nj_ren_x`              | New `is_504`             | A new column null-fills mid-rollout. A retype fails the union until all 3 districts rebuild.     |
| Past enrollment with no `S_NJ_REN_X` | Fall back to `S_NJ_STU_X`; `false`; null                                                             | `S_NJ_STU_X` (proposed)  | Keeps about 490 old Newark and Camden flags that `false` would drop, and uses the state field.   |
| School years                         | All years; current year only                                                                         | All years (user)         | One definition, matching what NJ received. Current-year-only keeps a split at the year boundary. |
| Follow-up                            | One-time worklist in Google Sheets; recurring dbt-fed sheet                                          | One-time worklist (user) | Fastest path to correcting records. A recurring check waits on #6350 for the EdPlan side.        |

## Design

### PR 1: `powerschool` package

- `src/dbt/powerschool/models/sis/staging/dlt/stg_powerschool__s_nj_stu_x.sql`:
  add `if(pid_504_tf = 1, true, false) as is_504`. The NJ docs give the field a
  default of No, so null reads false.
- `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__s_nj_stu_x.yml`:
  add `is_504` as `boolean`, with a description and
  `config.meta.contains_pii: true` (tier 3 in `.claude/rules/ferpa-pii.md`).
- Leave the disabled odbc and sftp variants alone.
- PR body says `Refs #6354`.

### Between the PRs

- Confirm all 3 district prod tables
  (`kipp{newark,camden,paterson}_powerschool.stg_powerschool__s_nj_stu_x`) carry
  `is_504`, and that the kipptaf union view exposes it.
- Build and deliver the worklist (below).

### PR 2: kipptaf

- `int_students__student_enrollments.sql`: change the NJ branch from
  `coalesce(njr.pid_504_tf, suf.is_504, false)` to
  `coalesce(njr.pid_504_tf, njs.is_504, false)`, and update the comment above
  it. `njs` is already joined. `njr.pid_504_tf` is null only when no
  `S_NJ_REN_X` row exists, because its staging maps null to false.
- `int_students__student_enrollments.yml`: rewrite the `is_504` description.
- Keep the `suf` join. Other columns still come from it.
- Before CI, refresh each district's `zz_stg_<district>_powerschool` copy of
  `stg_powerschool__s_nj_stu_x`. That is a shared staging write and needs the
  user's go-ahead.
- PR 2's branch links to #6354, and its body says `Closes #6354`.
- If #6284 merged first, rerun its DDI Suite comparison after PR 2.

### Expected effect

Flagged enrollment rows, measured on 2026-11-10:

| Region   | School years       | Today | After |
| -------- | ------------------ | ----: | ----: |
| Newark   | 2026–27            |    83 |    86 |
| Camden   | 2026–27            |    46 |    48 |
| Paterson | 2026–27            |     0 |    11 |
| Newark   | 2021–22 to 2025–26 |   724 |   702 |
| Camden   | 2021–22 to 2025–26 |   268 |   260 |
| Paterson | 2021–22 to 2025–26 |    11 |    11 |
| Newark   | before 2021–22     |   791 |   709 |
| Camden   | before 2021–22     |   154 |   135 |

The SY2025-26 CRDC roster gains 1 Camden student in the 504-only count. STAT is
unaffected because it reads the state test file.

### Worklist

A Google Sheet in the user's Drive, unshared until the user shares it. It is
built from a script in the session scratchpad and never committed.

- Tabs: Newark, Camden, Paterson, and Summary.
- Rows: currently enrolled students in one of these groups.
  1. `C_504_STATUS` set, `PID_504_TF` not set: the flag turns off.
  2. `PID_504_TF` set, `C_504_STATUS` not set: the flag turns on.
  3. EdPlan shows a current 504 plan, `PID_504_TF` not set.
  4. `PID_504_TF` set, EdPlan shows no current plan, a lapsed plan, or a
     non-eligibility decision.
- Columns: school, grade, student number, name, `PID_504_TF`, `C_504_STATUS`,
  EdPlan status, EdPlan plan end date, group, suggested fix, and a blank notes
  column for the person working the row.
- EdPlan status for Newark comes from the "TEAM 504 - 20261110" export: its
  current-plan rows, plus the R100 eligibility report for lapsed plans.
- Summary tab: counts by region and group, and counts of exited students whose
  past-year flag changes. Exited students get no rows to work.
- Delivered before PR 2 merges. PR 2 does not wait for schools to finish.

## Left to the builder

- Exact description wording for both `is_504` columns.
- Suggested-fix wording in the worklist.
- Whether Camden gets an EdPlan column. That depends on getting a Camden export
  of the same report. Without one, Camden's tab uses groups 1 and 2 only.
