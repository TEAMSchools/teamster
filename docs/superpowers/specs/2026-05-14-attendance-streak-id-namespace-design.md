# Namespace the two surrogate-key branches in `int_powerschool__attendance_streak`

Refs #3917. Follow-up to #3916.

## Problem

`int_powerschool__attendance_streak.streak_id` is not unique within
`(studentid, yearid)` in Paterson. CI on #3916 surfaced 305 dup groups (610
rows; all Paterson; AY 2023–24 and 2024–25). Each group is two rows with the
same `streak_id` but legitimately distinct `streak_start_date` /
`streak_end_date` / `streak_length`.

## Root cause

The model performs two independent gaps-and-islands passes and unions them:

- **code branch** — hash inputs
  `[project_name, studentid, yearid, att_code, (membership_day_number − rn_student_year_code)]`
- **att branch** — hash inputs
  `[project_name, studentid, yearid, attendancevalue, (membership_day_number − rn_student_year_attendancevalue)]`

`dbt_utils.generate_surrogate_key` stringifies each input before hashing. The
4th input differs by name but coincides in string form when:

- `att_code` is a numeric character (`'1'`, `'2'`, …), AND
- the corresponding `attendancevalue` in the other branch stringifies to the
  same digit (`1` → `'1'`), AND
- the two gaps-and-islands diffs happen to align.

When all three conditions hold, the two branches produce identical hashes for
two unrelated streaks.

This is Paterson-only because only Paterson's PowerSchool config uses numeric
`att_code` values (`1`–`5`, 7,825 rows). Newark / Camden / Miami use purely
alphabetic codes, so cross-branch collision is structurally impossible there.

Confirmed by inspecting one colliding group:

- Student S, yearid 33, dates 2023-08-15 (1 day, att_code=`'1'`,
  attendancevalue=0) → code branch produces hash `2507c23b…` from
  `(project, sid, 33, '1', 1)`.
- Same student, dates 2023-08-16..2024-06-14 (178 days, att_code=`null`→`'P'`,
  attendancevalue=1) → att branch produces hash `2507c23b…` from
  `(project, sid, 33, 1, 1)`.

The 4th and 5th inputs match across branches; the unioned `streak_id` collides.

## Fix

Prepend a literal `'code'` / `'att'` discriminator as the first hash input of
each `generate_surrogate_key` call. This namespaces the two branches such that
no input alignment between them can produce identical hashes.

### Changes

1. **`src/dbt/powerschool/models/sis/intermediate/int_powerschool__attendance_streak.sql`**
   — add `"'code'"` and `"'att'"` as the first element of each
   `generate_surrogate_key` argument list.

2. **`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__attendance_streak.yml`**
   — add `unique` test on the `streak_id` column with `config: severity: error`,
   plus a model `description` and column `description`s where missing (per
   `src/dbt/CLAUDE.md` intermediate-layer requirements).

3. **`src/dbt/kipptaf/models/marts/facts/properties/fct_student_attendance_streaks.yml`**
   — remove the `# TODO(#3917)` comment block and the `config: severity: warn`
   override on `student_attendance_streak_key.unique`, restoring the test to
   default severity (`error`).

The per-district intermediate test (single-column `unique` on `streak_id`) is
sufficient — the kipptaf `union_relations` view inherits uniqueness on
`(streak_id, _dbt_source_relation)` automatically, and the kipptaf-level view
intentionally carries no own tests per `src/dbt/kipptaf/CLAUDE.md` ("Uniqueness
tests and `materialized: table` belong on the per-region source-system staging
models, not on the kipptaf-level view").

## Hash-change implications

Every `streak_id` value changes (the hash inputs change shape).
`fct_student_attendance_streaks.student_attendance_streak_key` =
`generate_surrogate_key([st.streak_id, st._dbt_source_relation])` also churns in
lockstep. Per `src/dbt/kipptaf/models/marts/CLAUDE.md` spec-authoring context
(no production consumers of the mart yet), this churn is free. No non-mart
consumers hash on `streak_id` directly — verified by:

```sh
rg "generate_surrogate_key.*streak_id" src/dbt
```

(Expected: only `fct_student_attendance_streaks`.)

## Acceptance

- [ ] `int_powerschool__attendance_streak.streak_id` has a `unique` test at
      `severity: error` in the source-system properties yml.
- [ ] `fct_student_attendance_streaks.student_attendance_streak_key.unique` is
      restored to default severity (`error`) — the warn override and
      `TODO(#3917)` comment block from #3916 are removed.
- [ ] `uv run dbt build --select int_powerschool__attendance_streak+` from each
      district worktree (kippnewark, kippcamden, kippmiami, kipppaterson) passes
      uniqueness.
- [ ] `uv run dbt build --select fct_student_attendance_streaks` from
      `src/dbt/kipptaf` passes uniqueness.
- [ ] dbt Cloud CI on the PR returns zero failing rows on both tests.

## Out of scope

- Auditing why Paterson's PowerSchool uses numeric `att_code` values. The fix is
  robust to any future district adopting numeric codes; no SIS configuration
  change is required.
- Investigating whether the att-branch UNION ALL output is consumed anywhere
  downstream (it produces a coarser view of the code-branch streaks). Removing
  it is a separate scope.
