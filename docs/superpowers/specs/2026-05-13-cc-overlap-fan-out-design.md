# Collapse CC Overlap Fan-Out (`#3900`)

## Context

Three mart facts carried `qualify row_number() = 1` tiebreakers citing `#3633`:

- `fct_student_attendance_daily`
- `fct_student_attendance_streaks`
- `fct_grades_assignments`

`#3633` was actually about `int_people__location_crosswalk` deduplication and
closed 2026-04-22. `#3900` was filed to retarget the references and build a
canonical upstream enrollment model.

Empirical verification on 2026-05-13 changed the picture:

- `base_powerschool__student_enrollments` has **0 overlapping date ranges**
  today (issue claimed 3 pairs on 2026-05-12 — transient or measurement
  artifact).
- `base_powerschool__course_enrollments` has 607 overlap pairs, but **0 of
  them** are between two active enrollments. Every overlap involves at least one
  `is_dropped_section = true` row.
- After `where not is_dropped_section`, residual fan-out at the
  `fct_grades_assignments` join site drops from 6,594 extra rows to ~71.
- The underlying source-data anomaly is PowerSchool double-writing `cc` records
  for the same `(studentid, sectionid, dateleft)`. 24 dup groups / 48 rows
  total, **all from AY 2023 or earlier** — the corpus is frozen. Concentrated in
  Newark (19 groups), with Miami (3) and Camden (1). Paterson is clean.
- The two attendance qualifies are **no-ops** at current data (0 fan-out at
  their join sites).

## Goals

1. Drop the misleading `qualify` tiebreakers and the stale `#3633` references.
2. Surface the PowerSchool source-data anomaly at its origin with a warn-level
   test, so growth in the corpus is observable.
3. Apply the semantic fix that prevents dropped enrollments from anchoring
   gradebook assignments.
4. Update `src/dbt/CLAUDE.md` so future work follows the new pattern rather than
   reaching for `qualify`.

## Non-Goals

- Building a canonical upstream enrollment model. Not warranted —
  `student_enrollments` has no overlap, and the `course_enrollments` anomaly is
  a small frozen corpus.
- Adding defensive `dbt_utils.deduplicate()` to mask the residual duplicates.
  The mart PK uniqueness test is expected to fail until Ops cleans the source —
  that failure is the pressure signal.
- Fixing the `base_powerschool__course_enrollments` sections-join amplification
  (4× in Newark, 2× in Camden, 3.6× in Miami). Separate concern, file as a
  follow-up if needed.
- Touching `int_extracts__student_enrollments` or
  `base_powerschool__student_enrollments`.

## Changes

### 1. Upstream warn test on `stg_powerschool__cc`

Add `dbt_utils.unique_combination_of_columns` test on
`(studentid, sectionid, dateleft)` with `severity: warn` to
`src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__cc.yml`.

```yaml
data_tests:
  - dbt_utils.unique_combination_of_columns:
      arguments:
        combination_of_columns: [studentid, sectionid, dateleft]
      config:
        severity: warn
```

Expected: flags 24 dup groups / 48 rows. Stable corpus (no AY 2024–2026
incidents); growth would indicate a new source-system issue.

Coexists with the existing PK uniqueness test (presumably on `id` or `dcid` —
verify before edit).

### 2. Dropped-section filter in `fct_grades_assignments`

In the `course_enrollments` CTE at the top of
`src/dbt/kipptaf/models/marts/facts/fct_grades_assignments.sql`, add
`where not is_dropped_section`. Semantically correct: a gradebook assignment
shouldn't anchor on a dropped enrollment record. Drops 6,523 of the 6,594
fan-out rows.

### 3. Drop `qualify` from `fct_grades_assignments`

Remove the `qualify row_number() over (...) = 1` block at the end of
`fct_grades_assignments.sql` (currently lines 127–134). Do not replace with
`dbt_utils.deduplicate()`. Residual ~71 violating rows from historical PS source
duplicates will surface in the mart PK uniqueness test.

### 4. Drop `qualify` from `fct_student_attendance_daily`

Remove the `qualify` block at lines 99–106 of
`fct_student_attendance_daily.sql`. Verified no-op (0 fan-out at the join site).
Confirm by row-count diff between the dev build of this branch and the prod
table — must match.

### 5. Drop `qualify` from `fct_student_attendance_streaks`

Same as above for lines 44–46 of `fct_student_attendance_streaks.sql`. Verify
no-op with row-count diff.

### 6. Mart PK uniqueness test severity

Leave `fct_grades_assignments` PK uniqueness test at `severity: error` (do not
downgrade to warn). Test will fail in CI until source records are cleaned by
Ops. dbt test failures do not block downstream materialization, so consumers
continue to receive data — they will see ~71 duplicate rows for historical grade
assignments until cleanup. Document this in the PR description.

### 7. Update `src/dbt/CLAUDE.md`

Rewrite the "Enrollment join fan-out (known upstream issue)" section (currently
lines 355–362) to:

- Cite `#3900` instead of `#3633`.
- State that PowerSchool double-writes `cc` records for some
  `(student, section, dateleft)` tuples; tracked by the warn test on
  `stg_powerschool__cc` and `#3900`. Historical corpus only; no active-year
  incidents.
- When date-range joining `base_powerschool__course_enrollments`, filter
  `is_dropped_section` first.
- Do not add defensive dedupes (`qualify` or `dbt_utils.deduplicate`) to mask
  residual source-data dupes. A failing mart PK test is the signal Ops needs to
  clean source.
- `base_powerschool__student_enrollments` date-range joins do not currently need
  any tiebreaker.

### 8. Close issue `#3900`

Post a verification comment summarizing:

- Original claim of 3 overlapping student-enrollment pairs did not reproduce on
  2026-05-13.
- Real anomaly is `course_enrollments`: 24 dup groups / 48 rows, frozen corpus
  AY ≤ 2023.
- Regional breakdown: Newark 19, Miami 3, Camden 1, Paterson 0.
- Resolution: warn test upstream + semantic dropped-section filter
  - remove misleading qualifies. Mart PK test left at error severity pending Ops
    cleanup. Source cleanup tracked as `#3915`.

Close on merge.

### 9. Ops cleanup tracker (already filed)

`#3915` (`chore(powerschool): clean up double-written cc records`) tracks Ops
cleanup of the 24 historical PS source records. PR body should reference both
`#3900` (closes) and `#3915` (refs).

## Verification Gates

Run from worktree root:

```bash
uv run dbt build \
  --select fct_student_attendance_daily fct_student_attendance_streaks fct_grades_assignments stg_powerschool__cc \
  --project-dir src/dbt/kipptaf
```

Expected outcomes:

- `fct_student_attendance_daily` model + PK test: pass.
- `fct_student_attendance_streaks` model + PK test: pass.
- `fct_grades_assignments` model: pass.
- `fct_grades_assignments` PK uniqueness test: **expected to fail** with ~71
  violating rows (historical PS bookkeeping artifacts). Capture exact count for
  the PR description.
- `stg_powerschool__cc` warn test: surfaces 24 failing groups.
- Trunk lint clean.

Row-count diffs (dev vs. prod):

- `fct_student_attendance_daily`, `fct_student_attendance_streaks`: expected
  unchanged.
- `fct_grades_assignments`: expected to drop by the count of grade rows whose
  due-date fell during a dropped-section window. Capture the delta in the PR
  description.

## Risks

- **PR carries a known-failing test.** Reviewers will see a red PK test on
  `fct_grades_assignments`. The PR description must clearly flag this as
  intended pressure on Ops, not a regression.
- **Downstream consumers see ~71 duplicate grade rows** for historical
  assignments. Cube/Tableau exposures may need a heads-up if anyone reports
  inflated counts on pre-2024 data.
- **Sections-join amplification** in `base_powerschool__course_enrollments`
  (2–5× by region) remains untouched. If a future mart joins CC on a different
  grain, it may hit the amplified fan-out and require its own filter logic.

## Out-of-Scope Follow-Ups

- Investigate Paterson's PowerSchool process — they're the only clean region.
  Replicating their workflow elsewhere could eliminate the anomaly at source.
- Audit `base_powerschool__course_enrollments` sections-join amplification
  (separate issue if Ops wants to act on it).
- Newark 2020 cluster (10 dup groups) is the densest concentration — COVID-era
  enrollment churn likely; potential one-shot cleanup target.
