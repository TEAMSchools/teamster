# Miami archive sources, warn pins, and the uncovered-calendar-day test

Refs [#4750](https://github.com/TEAMSchools/teamster/issues/4750).

Covers items 2, 3, and 4 of that issue's "What this issue needs next" list. Item
1 is Ops work tracked in Asana. Item 5 became
[#5390](https://github.com/TEAMSchools/teamster/issues/5390).

## Problem

Three unrelated defects share one diagnostic re-run, so they ship together.

**Item 2.** Thirteen dbt tests carry the comment
`# TODO(#5305): failing today; resolve then drop the warn` above their
`severity: warn`. Issue #5305 closed on 2026-09-15 by #5322. The pins now point
at a closed issue.

**Item 3.** Miami's frozen PowerSchool archive holds calendar, term, and
enrollment relations that kipptaf never reads. The four kipptaf
`union_relations` wrappers union Newark, Camden, and Paterson only, so Miami's
pre-Focus history is absent from every network calendar and term model.

**Item 4.** `int_powerschool__calendar_day` left-joins `stg_powerschool__terms`
on `isyearrec = 1`. A school day that no year term covers keeps a null `yearid`
and a null `academic_year`. 157 such days are `insession = 1` at a real school
across the three NJ districts.

## What the diagnostic re-run changed

Three findings contradict the issue body. Each changes the design.

### The pins do not belong at all, so nothing gets re-pointed

The issue asks to re-point the 13 pins at a live issue. Re-pointing assumes each
test has a resolvable end state, after which the `warn` drops and the test goes
back to `error`.

None of them does. Every one monitors recurring data entry: an `fteid` scoped to
the wrong school year, a pair of overlapping enrollment stints, a same-day exit
and re-entry, an unmapped Focus phone-contact title, a multi-day
course-enrollment overlap. Ops corrects the rows, and the next month's entry
produces new ones. None reaches a stable zero, so "resolve then drop the warn"
is a promise none of them can keep.

The repo already has the shape these tests want. Two `severity: warn` tests
carry no pin: `test_int_powerschool__gpa_cumulative_year__reconciles_stored` and
`int_students__calendar_day__zero_enrollment_in_session_days`. The second one's
comment says the fix belongs in Focus configuration, not in dbt. Both are
permanent standing monitors, and that is what all 13 pinned tests are too.

So item 2 deletes the pins and keeps every `severity: warn`.

### One test's description names the wrong issue

`int_powerschool__student_enrollment_union_no_shared_stint_boundary` describes
itself as "Source defect surfaced by issue #3902". #3902 is closed, and its
subject is orphaned survey submissions in `fct_survey_submissions`, not
enrollment stint boundaries. The reference is wrong on both counts and goes with
the pins.

Contrast `#3915`, referenced by
`base_powerschool__course_enrollments__no_studyear_course_overlap`. That issue
is open, labeled `ops-tracked`, and genuinely tracks the 10,807 overlapping
study-year course enrollments the test counts. It stays.

### Item 4 gets a test, not a model change

The issue frames item 4 as a fix to `int_powerschool__calendar_day`. Deriving
`academic_year` from `date_value` instead of from the term join would make the
null go away, and that is the reason not to do it.

The null is a true signal. Paterson's academic year 2024 year term runs
2024-09-03 through 2025-06-20 at both real schools. The 30 uncovered Paterson
days at those schools sit at 2024-08-19 through 2024-09-02, 15 per school,
before the school year's own first day, and 11 of them are marked in session.
PowerSchool holds a calendar that disagrees with its own term record. A derived
`academic_year` would paper over that and leave the source defect invisible.

The defect is also inert. Zero student-day membership rows exist on any
uncovered day in any district. This is not circular:
`int_powerschool__ps_membership_reg` joins `stg_powerschool__calendar_day`, not
`int_powerschool__calendar_day`, on `schoolid` plus a date range plus
`insession = 1`, and never reads `yearid`. Populating `academic_year` cannot
create a membership row or move an average-daily-attendance denominator.

An inert source defect with no downstream effect is exactly what a warn-severity
test is for.

## Decision

### Item 2 — delete 13 pins and one wrong issue reference

Delete the comment line
`# TODO(#5305): failing today; resolve then drop the warn` at each of these
locations. Change nothing else on those tests: every `severity: warn` stays, and
every `meta.dagster.ref` stays.

| File                                                                                            | Lines           |
| ----------------------------------------------------------------------------------------------- | --------------- |
| `src/dbt/finalsite/tests/properties.yml`                                                        | 11, 45, 66, 83  |
| `src/dbt/focus/tests/properties.yml`                                                            | 59, 104, 125    |
| `src/dbt/powerschool/tests/properties.yml`                                                      | 15, 41, 58, 102 |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__ps_enrollment_all.yml` | 11, 20          |

In `src/dbt/powerschool/tests/properties.yml`, also drop the sentence fragment
"Source defect surfaced by issue #3902 —" from
`int_powerschool__student_enrollment_union_no_shared_stint_boundary`'s
description, leaving the row count that follows it.

`.claude/rules/dbt-yaml.md` already forbids tracking-issue references in a
`description:`. Removing this one brings the file into line with that rule.

### Item 3 — declare five Miami relations and add them to five wrappers

Add five tables to `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`
under the existing `kippmiami_powerschool` source, each following the file's
established block shape with
`config.meta.dagster.asset_key: [kippmiami, powerschool, <name>]`:

- `int_powerschool__calendar_day`
- `int_powerschool__calendar_week`
- `int_powerschool__terms`
- `int_powerschool__student_enrollment_union`
- `stg_powerschool__terms`

Then add one `source("kippmiami_powerschool", "<name>")` line to each of the
five matching kipptaf wrappers:

| Wrapper                                                                         | Sole consumer                            |
| ------------------------------------------------------------------------------- | ---------------------------------------- |
| `models/powerschool/intermediate/int_powerschool__calendar_day.sql`             | `int_students__calendar_day`             |
| `models/powerschool/intermediate/int_powerschool__calendar_week.sql`            | `int_students__calendar_week`            |
| `models/powerschool/intermediate/int_powerschool__terms.sql`                    | `int_students__terms`                    |
| `models/powerschool/intermediate/int_powerschool__student_enrollment_union.sql` | `int_students__student_enrollment_union` |
| `models/powerschool/staging/stg_powerschool__terms.sql`                         | `int_students__terms`                    |

The fifth relation, `stg_powerschool__terms`, is not in the issue body.
`int_students__terms` reads it directly for the quarter-grain side of its
PowerSchool branch, so leaving it out would wire Miami's year terms into the
network while its quarter terms stayed missing.

Also update the `rn` comment in `stg_powerschool__terms.sql`. It currently reads
"all 2,139 keys across the four districts are singletons" while the union covers
three. With Miami added the union really is four districts, and the verified
count today is 2,118 keys with zero duplicates, of which 193 are Miami's.

The kipptaf consumer topology is strictly one-to-one, so nothing else in the
project sees a row-set change.

This is a source declaration plus a `union_relations` argument, so it is a
single-PR change under `.claude/rules/dbt-models.md`: no district model changes,
no new columns, no two-PR staging dance.

### Item 4 — one singular test on the uncovered in-session day

Add
`src/dbt/powerschool/tests/test_int_powerschool__calendar_day__in_session_day_has_year_term.sql`:

```sql
select _dbt_source_relation, schoolid, date_value, school_name,
from {{ ref("int_powerschool__calendar_day") }}
where academic_year is null and insession = 1 and schoolid not in (0, 999999)
```

`academic_year` is null exactly when no `isyearrec = 1` term covers the day, so
the null is the whole predicate. No second join is needed.

Declare it in `src/dbt/powerschool/tests/properties.yml` with `severity: warn`,
no pin, a description that states what the defect is and where the fix belongs,
and:

```yaml
meta:
  dagster:
    ref:
      name: int_powerschool__calendar_day
      package: powerschool
```

`package: powerschool` is required. Without it dagster-dbt resolves the ref
against the running district project and logs an `AssetObservation` across every
parent instead of an `AssetCheckResult` on the intended asset.

The `schoolid not in (0, 999999)` scope follows the precedent in
`int_students__calendar_day__zero_enrollment_in_session_days`. Sentinel schools
0 and 999999 carry junk full-year in-session calendars. Leaving them in adds 59
rows of noise and buries the real ones.

## Verification

Every number below was measured against prod on 2026-09-17.

**Item 2.** `dbt parse --no-partial-parse` on `main` and on the branch, then
diff the `resource_type == 'test'` node names. The diff must be empty: this
change deletes comments and prose, not nodes. Parse both sides fresh, per
`.claude/rules/dbt-models.md`.

**Item 3.** All five Miami relations exist as frozen tables with column sets
identical in name and type to Newark's, so `union_relations` grows no superset
and adds no null-filled column:

| Relation                                    | Columns (Miami and Newark) |
| ------------------------------------------- | -------------------------- |
| `int_powerschool__calendar_day`             | 30                         |
| `int_powerschool__calendar_week`            | 20                         |
| `int_powerschool__terms`                    | 8                          |
| `int_powerschool__student_enrollment_union` | 49                         |
| `stg_powerschool__terms`                    | 29                         |

Date ranges are disjoint, so nothing double-counts. The Miami archive covers
academic years 2017 through 2025. The Focus branch of
`int_students__calendar_day` floors at `focus_start_academic_year`, which
is 2026. No cutover ceiling is added to the PowerSchool branch: that branch is
network-wide and New Jersey has no Focus, so a ceiling would truncate all three
NJ districts at 2026. Disjointness is asserted by query instead:

```sql
select academic_year, count(*)
from {{ ref("int_students__calendar_day") }}
where _dbt_source_project = 'kippmiami'
group by 1 order by 1
```

Every academic year must appear once, never split across the two branches.

Validate the new wrapper column lists with
`dbt compile --select <wrapper> --target staging`. A dev-target compile expands
to nothing because the dev dataset holds no copy of the source relations, and an
empty expansion still compiles clean.

**Item 4.** The test must fail with 157 rows at warn severity:

| District       | Rows | Schools |
| -------------- | ---- | ------- |
| `kippnewark`   | 104  | 13      |
| `kippcamden`   | 42   | 3       |
| `kipppaterson` | 11   | 1       |

`kippmiami` holds 4 more such days but is not monitored: it does not consume the
`powerschool` package, following the same limitation already documented on
`base_powerschool__course_enrollments__no_studyear_course_overlap`.

Run `uv run dbt build --select int_powerschool__calendar_day+` per NJ district.

## Out of scope

**Item 5**, the `int_students__attendance_daily` term join, is #5390.
Re-measured today it drops 1,864,931 membership rows, not the approximately
3,890,000 the #4750 comment estimated. That issue also carries two latent
defects in `int_students__terms`: the PowerSchool branch's `full join`, and an
`and p.rn = 1` predicate inside that join's `ON` clause that does not filter
`p`.

Items 3 and 5 interact. Miami contributes 492,482 of the 1,864,931 dropped rows,
and academic years 2018 and 2019 are 100 percent unmatched for Miami because
`int_students__terms` carries no Miami PowerSchool terms today. Item 3 should
recover part of that with no change to `int_students__attendance_daily`. How
much is not measured. Re-run #5390's reproduce query after this PR merges.

**`int_powerschool__ps_membership_reg`** stays declared and unconsumed in
`sources-kippnewark.yml`. It is a source declaration with no kipptaf model and
no Dagster, Cube, or exposure consumer, and it is one of roughly 55 such orphans
in that file, alongside `stg_powerschool__sections`, `stg_powerschool__person`,
`int_powerschool__ps_enrollment_all`, and the whole graduation-plan family.
Deleting this one singles out an arbitrary member of an established pattern. The
orphan sweep is its own issue and is not filed yet.

**The Ops backlog behind the 13 warn tests.** Deleting the pins does not create
Asana tasks for the underlying data-entry defects. Those defects are real and
recurring, but the warn tests are the tracking mechanism now, and whether Ops
also wants standing tasks is a separate call.

## Alternatives considered

**Re-point the 13 pins at a new umbrella issue.** Rejected. It preserves a
promise none of the tests can keep and produces an issue that can never close.

**Derive `academic_year` from `date_value` in `int_powerschool__calendar_day`.**
Rejected. It hides a true source defect and buys nothing, since no downstream
model reads those rows.

**Add a cutover ceiling to the kipptaf PowerSchool calendar branch.** Rejected.
The branch is network-wide, so a ceiling at `focus_start_academic_year` would
truncate Newark, Camden, and Paterson at academic year 2026. The archive's own
AY2025 bound already makes the two branches disjoint.

**Fold item 5 into this PR.** Rejected by the user. It is a behavior change to
network attendance reporting, it needs its own consumer audit for null `term`
and `semester`, and it is the only one of the four that moves a published
metric.
