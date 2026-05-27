# Strip stale `#3633` references in dbt marts + verify residual workarounds

Date: 2026-05-23 Tracks:
[#3901](https://github.com/TEAMSchools/teamster/issues/3901) Spawns:
[#4020](https://github.com/TEAMSchools/teamster/issues/4020)

## Context

Issue #3901 listed seven files carrying stale `-- TODO: #3629 / #3633 / #3635`
references to closed issues, asking for a doc-only ref refresh. Verification on
2026-05-23 showed the issue body is materially stale:

- All originally-listed survey-domain files (`fct_survey_submissions`,
  `dim_survey_administrations`, `dim_surveys`, `dim_survey_questions`,
  `bridge_survey_questions`) have zero remaining stale refs — fully refactored
  when #3899 closed (2026-05-14).
- All originally-listed attendance/grades facts (`fct_student_attendance_daily`,
  `fct_student_attendance_streaks`, `fct_grades_assignments`) have zero
  remaining stale refs — fixed via #3916 (closes #3900, 2026-05-14).
- The originally-listed `src/dbt/CLAUDE.md` "Enrollment join fan-out" guidance
  was relocated to `src/dbt/kipptaf/CLAUDE.md` "Known Upstream Issues" in #3916;
  the relocated text at line 121 still carries `(#3633)`.

Two consumers of the same upstream-overlap pattern that #3900 was meant to
eliminate were **not** in #3900's acceptance scope and still carry the
workaround comments referencing `#3633`:

- `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql:58`
- `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql:442`

Empirical verification (prod, 2026-05-23) shows these two are not equivalent:

- `dim_student_section_enrollments` dedup is a **no-op** — 0 fan-out / 784,568
  cc rows. The half-open interval join (`>= entrydate AND < exitdate`) already
  prevents the overlap.
- `rpt_gsheets__school_metrics_extract` `SELECT DISTINCT` is **load-bearing** —
  collapses 50 multi-stint same-school enrollments (Newark 26, Camden 10, Miami
  8, Paterson 6) for AY 2025 / grade ≤ 8. Cause is multi-stint enrollments
  (transfer out + back), not the date-range overlap pattern #3900 originally
  described. Tracked separately in #4020.

## Changes

### 1. `src/dbt/kipptaf/models/marts/dimensions/dim_student_section_enrollments.sql`

Remove the no-op `course_enrollments_deduped` CTE and its TODO comment. Remove
the `# trunk-ignore(sqlfluff/ST03)` directive on `course_enrollments_joined` (no
longer needed once that CTE is referenced directly by name in the final SELECT).
Final `from course_enrollments_deduped` becomes
`from course_enrollments_joined`.

Hash inputs unchanged. Row count unchanged (verified above).

### 2. `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql:442`

Keep `select distinct` (project rule allows DISTINCT with a TODO). Rewrite the
comment to drop `#3633` and accurately describe the multi-stint cause, pointing
at #4020:

```sql
-- TODO: #4020 — int_extracts__student_enrollments carries one row per
-- enrollment stint, so a student with a transfer-out + transfer-back at the
-- same school produces duplicate (studentid, schoolid) rows. SELECT DISTINCT
-- collapses them for the downstream join. enroll_status filter intentionally
-- omitted: a wider net is needed so transferred students' section records
-- still resolve to a school/region even when their latest enrollment row has
-- enroll_status != 0.
```

### 3. `src/dbt/kipptaf/CLAUDE.md:121`

Strip the trailing `(#3633)` parenthetical. The surrounding paragraph documents
the canonical-grain guidance on its own merits.

## Verification

- `uv run dbt parse --project-dir <worktree>/src/dbt/kipptaf` — no errors.
- `uv run dbt build --select dim_student_section_enrollments+1 --project-dir <worktree>/src/dbt/kipptaf`
  against the PR-branch schema — row count matches prod, uniqueness test passes.
- Trunk fmt/check fires via pre-commit and pre-push hooks.
- dbt Cloud CI: PR-branch build of `dim_student_section_enrollments` should
  match prod row-for-row (no-op dedup removal).
  `rpt_gsheets__school_metrics_extract` diff is comment-only.

## Out of scope

- Migrating the `rpt_gsheets` `select distinct` to `dbt_utils.deduplicate`, or
  building a per-(student, school) helper on `int_extracts__student_enrollments`
  — tracked in #4020.
- Reopening #3900. Its closure via #3916 was correct per its own acceptance
  scope; the residual `rpt_gsheets` case is a different mechanism (multi-stint
  enrollments, not overlapping date ranges).
