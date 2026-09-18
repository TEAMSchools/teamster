# Miami terms: Focus from the cutover year, PowerSchool before it

Refs [#5397](https://github.com/TEAMSchools/teamster/issues/5397).

## Problem

`int_students__terms` sources every Miami term row from Focus. Focus carries
quarter rows for only 3 of Miami's 7 schoolids before AY2025, so 492,482 Miami
membership days in `int_students__attendance_daily` carry a null `term` and a
null `semester`. Measured against prod on 2026-09-18, out of 16,310,421 rows in
that model.

Those 492,482 days are two distinct gaps, not one:

| Gap                 | Days    | Cause                                                        |
| ------------------- | ------- | ------------------------------------------------------------ |
| Schools 30200801-02 | 442,576 | No Focus quarter row at all before AY2025                    |
| Schools 30200803-04 | 49,906  | Focus quarter windows are narrower than the archive calendar |

#5397 diagnosed only the first gap. Its proposed precedence rule — take an
archive quarter only where Focus has no row for that schoolid and academic year
— suppresses the archive for 30200803 and 30200804, so the second gap's 49,906
days stay null in every year through AY2025. That rule cannot deliver the
491,971 recovered days the issue's own coverage table promises.

## Decision

Focus is Miami's system of record for terms from the SIS cutover year onward.
The frozen PowerSchool archive is the system of record before it. This replaces
the anti-join framing in #5397 entirely.

The boundary is not a literal. `int_students__sis_cutover` already publishes it
as a single row, `focus_start_academic_year`, currently 2026, derived from
Focus's first year of recorded attendance. `int_students__attendance_daily`
already implements this exact rule against that model and documents the pattern
at its `powerschool_conformed` CTE: the archive needs no cutover predicate
because it cannot emit a row past AY2025, so only the Focus branch is floored.

`int_students__terms` adopts the same shape.

### Why the whole Focus branch is floored, not just its quarter rows

Flooring only the quarter rows would leave Focus supplying Miami's year and
semester rows across AY2018 to AY2025, which preserves the two Tableau models
that read `isyearrec = 1`. That narrower scope was considered and rejected: it
splits one model across two systems of record at different grains for the same
school-year, which is harder to reason about than a clean year boundary.

The narrower scope is also unnecessary. Every Miami school-year that
`rpt_tableau__gradebook_gpa` actually emits has an archive year record behind
it, and `rpt_tableau__student_course_grades` emits no Miami rows at all:

| Model                   | Miami school-years emitted            | Archive covers |
| ----------------------- | ------------------------------------- | -------------- |
| `gradebook_gpa`         | AY2020 sch. 03; AY2021-25 sch. 03, 04 | yes, all       |
| `student_course_grades` | none                                  | not applicable |

## Design

Five changes. No new model, no restructuring of the union.

### 1. Expose the Miami archive as a kipptaf source

`src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml` gains two table
entries under the existing `kippmiami_powerschool` source:
`int_powerschool__terms` and `stg_powerschool__terms`.

The source-level description needs more than the comment fix #5398 makes. It
currently reads "14 permanent tables in total. Enrollment stints and terms are
deliberately absent" and then repeats the false coverage claim. After this
change it is 16 tables, terms are present, and only enrollment stints stay
absent — Focus really is Miami's sole enrollment source across all years, which
is the one half of that sentence that was always correct. The description is
rewritten to say terms follow the same cutover split the calendars already
follow, which the same paragraph already describes correctly for
`int_students__calendar_day` and `int_students__calendar_week`.

### 2. Union Miami into both kipptaf wrappers

`int_powerschool__terms.sql` and `stg_powerschool__terms.sql` each add
`source("kippmiami_powerschool", "<relation>")` to their
`dbt_utils.union_relations` list, and each drops the comment claiming Focus
already supplies Miami terms across the archive range.

Both are safe to widen. Verified against prod 2026-09-18: Miami's
`int_powerschool__terms` and Newark's carry the same 8 columns at the same
types, and their `stg_powerschool__terms` carry the same 29 columns at the same
types. `union_relations` therefore needs no null-fill. Neither wrapper enforces
a contract, so no column list needs regenerating.

`stg_powerschool__terms` derives `rn` in the wrapper, partitioned by schoolid,
yearid, abbreviation and source project, so Miami gets it for free. Miami's 193
archive rows hold 193 distinct keys, so `rn = 1` drops nothing, matching the New
Jersey districts. The wrapper comment's singleton count rises from 1,925 to
2,118.

### Nothing here belongs in the shared powerschool package

Adding Miami introduces no new join and no new calculation. It appends one
relation to an existing `union_relations` list, and the two wrapper expressions
that then run over it, `extract_source_project()` and `rn`, already exist and
are unchanged.

Of those two, only `rn` is even a candidate for promotion, and it should not be
promoted:

- `extract_source_project()` cannot move. `src/dbt/kipptaf/CLAUDE.md` is
  explicit that it belongs only on the `union_relations` view that creates
  `_dbt_source_relation`, and downstream models pass the materialized column
  through rather than re-deriving it. A source-system package has no cross-
  district union to derive it from.
- `rn` should not move, and Miami is the reason. The package's
  `stg_powerschool__terms` is contract-enforced, so adding a column there is a
  district-first two-PR ship. Worse, Miami's archive is frozen at an older
  package version: until it is rebuilt against the new one, `union_relations`
  would null-fill `rn` for Miami and the wrapper's `where rn = 1` would silently
  drop every Miami row. The guard is also defensive only — 2,118 singleton keys
  network-wide, zero duplicates — so promoting it buys nothing and couples a
  contract change to an archive rebuild.

The termbins-to-`terms` quarter fallback, the one piece of real logic in this
lineage, already lives in the package at `int_powerschool__terms` (#5396). That
is why the rebuild picks it up for free.

### 3. Floor the Focus branch at the cutover

In `int_students__terms.sql`, the `focus_marking_periods` CTE replaces its
`mp.syear >= 2018` literal with a cross join to the cutover model:

```sql
        cross join {{ ref("int_students__sis_cutover") }} as c
        where
            mp.type in ('year', 'semester', 'quarter')
            and mp.syear >= c.focus_start_academic_year
```

The 2018 floor becomes redundant: 2026 is above it. The existing comment
explaining why both filters live in this model rather than in staging still
applies to the marking-period type filter and is reworded, not deleted.

### 4. No predicate on the PowerSchool branch

`powerschool_quarters` and `powerschool_canonical` take no cutover filter. The
archive is bounded at AY2025 by its own rebuild post-hooks, which drop
`yearid > 35`, so it cannot collide with Focus. This follows the sibling
attendance model rather than adding a defensive predicate.

If that bound ever fails, the model's existing `unique_combination_of_columns`
on schoolid, yearid, term and source project scoped to `term is not null` fails
loudly. That test is the guard.

### 5. Correct the properties YAML

`properties/int_students__terms.yml` states that "Focus is Miami's system of
record for term definitions, so the frozen archive contributes no Miami rows."
That becomes false. The model description is rewritten to describe the year
boundary, and the per-column "For Miami, from Focus" notes are qualified to the
cutover year onward.

## What changes downstream

Verified consumer by consumer against prod. All 8 readers of
`int_students__terms` were checked.

| Consumer                                        | Effect                                                         |
| ----------------------------------------------- | -------------------------------------------------------------- |
| `int_students__attendance_daily`                | 492,482 null terms drop to 511. Row count unchanged.           |
| `int_students__enrollment_daily`                | Same class of recovery; joins on `term is not null`.           |
| `int_extracts__course_enrollments_by_term`      | Gains Miami rows for AY2020-25. Intended.                      |
| `int_extracts__course_schedule_by_term`         | Gains Miami rows for AY2020-25. Intended.                      |
| `rpt_tableau__gradebook_gpa`                    | Miami Y1 windows shift from Focus dates to archive dates.      |
| `rpt_tableau__student_course_grades`            | None. No Miami rows.                                           |
| `rpt_illuminate__terms`                         | None. Filters `_dbt_source_project != 'kippmiami'`.            |
| `int_tableau__gradebook_audit_teacher_scaffold` | None. Pins `academic_year = current_academic_year`.            |
| `int_extracts__student_enrollments_subjects`    | None. Inner-joins Miami-free `int_powerschool__spenrollments`. |

New Jersey output is unchanged by construction. No New Jersey schoolid appears
in Focus, so the floored branch never held a New Jersey row, and the two
wrappers gain a source rather than changing their existing arms. This must still
be measured, not assumed — see Verification.

### Rows that appear and rows that disappear

Miami term rows for school-years with no archive counterpart leave the model:
school 30200805 across AY2018-2024, schools 30200801, 30200802, 30200805,
30200806 and 30200807 in AY2025, school 30200803 in AY2018, and school 30200804
in AY2018 through AY2020. No consumer reads any of them, per the table above.

The archive brings in rows Focus never carried: schoolid 999999, PowerSchool's
graduated-students sentinel, for AY2022-2025; schoolid 30132008 for AY2018; and
schoolid 30200801 for AY2017, a year below Focus's old floor. These are left
unfiltered. The New Jersey arms already carry the same class of
non-instructional schoolid, no consumer joins to them, and the uniqueness tests
hold.

## Prerequisite: rebuild the Miami archive first

The archive's `int_powerschool__terms` is frozen at 72 rows, last written
2026-09-10, and predates #5396. Simulating #5396's `terms`-table fallback
against the archive's own staging tables yields 88 quarters, so the rebuild
adds 16.

The rebuild is required, not cosmetic. Two of the added school-years carry real
attendance: schoolid 30200801 in AY2018 and AY2019, worth 86,213 days. Without
the rebuild, 85,702 of them stay null and the change reads as a partial fix. The
other 8 added quarters, schoolids 30200801 and 30200802 in AY2023, cover no
attendance days and are inert.

The recipe is the `dbt_project.yml` `powerschool:` block in
`src/dbt/kippmiami/CLAUDE.md`: re-include the package with the ODBC staging
variant and its 16 post-hooks, build, then remove the package again. This is a
prod build and belongs in a human's terminal, not Claude's.

Ordering: rebuild, confirm 88 quarter rows, then open the wiring PR.

## The 511 residual days

Schoolid 30200801, AY2018, on 2019-06-12, 2019-06-13 and 2019-06-14. Q4's
`lastday` is 2019-06-11 while the year record `18-19` runs to 2019-06-28, so
PowerSchool's own quarter stops 3 instructional days short of its own year. No
fallback reading `terms.lastday` can close this.

These days stay null. A separate issue is filed against the PowerSchool source
data, and an inline comment at the derivation site references it.

## Verification

Run after the rebuild and before merge.

1. `int_students__attendance_daily` row count stays at 16,310,421. The recovered
   days already exist as rows; only `term` and `semester` change.
2. Miami rows in that model with a null `term` drop from 492,482 to 511, and all
   511 are schoolid 30200801 in AY2018.
3. New Jersey term rows are byte-identical before and after. Compare `count(*)`
   plus
   `count(distinct format("%T|%T|%T|%T", schoolid, yearid, term, abbreviation))`
   on the PR-branch build against prod, filtered to
   `_dbt_source_project != 'kippmiami'`.
4. Both `unique_combination_of_columns` tests on `int_students__terms` pass.
   These are what prove the precedence did not fan out the overlapping Miami
   school-years.
5. `rpt_tableau__gradebook_gpa` Miami row counts per academic year are unchanged
   from the prod baseline: 288, 1695, 2785, 6485, 7230, 7570 for AY2020 through
   AY2025.

## Out of scope

- The 3 false coverage comments are also touched by PR #5398. Let #5398 merge
  first and branch from `main`, or resolve the overlap at rebase.
- Miami tardy, suspension and period-grain attendance gaps, tracked in #4927.
- Any change to how the archive itself is built beyond the #5396 fallback the
  rebuild already picks up.
