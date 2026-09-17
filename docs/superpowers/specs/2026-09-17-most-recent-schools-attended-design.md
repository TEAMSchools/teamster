# Most-recent elementary and middle school attended

Design for [#5391](https://github.com/TEAMSchools/teamster/issues/5391). Written
2026-09-17.

Surface the elementary school and middle school a student attended on
`dim_students`, and expose both on all four student Cube views, so assessment
results can be cut by prior school.

## Problem

The student Cube views expose the student's current school only, through
`locations.abbreviation` on the enrollment join. An analyst cannot ask "how did
students from KIPP Rise Academy do on this interim."

The definition already exists outside the marts.
`int_extracts__student_enrollments` computes `ms_attended` and `es_attended` for
the Tableau dashboards, so the network has had this cut in Tableau for years and
has never had it in Cube.

## Decisions

Each of these was settled with the requester before the design was written.
Rationale is recorded so a later reader does not relitigate them.

- **Pick rule: most recent.** The existing Tableau columns pick the latest
  elementary or middle school, not the first. A student who transferred between
  two KIPP middle schools reports the later one. Alternatives considered and
  rejected: first attended, longest attended, terminal school in the band.
- **Population: mirror the existing definition.** Do not redefine who is in
  scope. This keeps the mart and the dashboards telling one story.
- **Names encode the rule.** `most_recent_elementary_school` and
  `most_recent_middle_school`. The plain phrase "elementary school attended"
  reads as "the school they started at," which is the opposite of what the rule
  does, so the column name carries the correction rather than relying on a
  description nobody opens.
- **Surface on all four student views**, not the assessment view alone. The
  `students` cube is joined by every student view, so a dimension on the student
  dim should behave the same everywhere.
- **The definition lives in a new shared intermediate.** `dim_students` reads
  it. Migrating `int_extracts__student_enrollments` to read it too is a
  follow-up, which means the definition sits in two places until that lands.
- **`es_graduated` stays out of scope.** It comes from the same window with a
  different input, so the follow-up migration closes the duplication for two of
  the three columns and leaves the window in place for the third.

## Design

### New model: `int_students__most_recent_schools_attended`

Lives at
`src/dbt/kipptaf/models/students/intermediate/int_students__most_recent_schools_attended.sql`.
Grain is one row per `student_number`, present only for students with at least
one elementary-band or middle-band stint.

```sql
with
    band_schools as (
        select
            student_number,
            school_level,
            school_abbreviation,
            academic_year,
            exitdate,
        from {{ ref("int_students__student_enrollments") }}
        where school_level in ('ES', 'MS') and school_abbreviation is not null
    ),

    # trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    most_recent as (
        {{
            dbt_utils.deduplicate(
                relation="band_schools",
                partition_by="student_number, school_level",
                order_by="academic_year desc, exitdate desc",
            )
        }}
    )

select
    student_number,

    max(
        if(school_level = 'ES', school_abbreviation, null)
    ) as most_recent_elementary_school,
    max(
        if(school_level = 'MS', school_abbreviation, null)
    ) as most_recent_middle_school,
from most_recent
group by student_number
```

Three properties of this SQL are load-bearing.

`dbt_utils.deduplicate` is required rather than preferred. The `row_number()`
plus `where rn = 1` form is gated in `.claude/rules/dbt-sql.md` on the dedup
input exceeding roughly 1 million rows **and** the model costing at least one
slot hour. This input is about 92,600 rows, so the macro form is the repo
default and the ranked form would be a convention violation.

`config: materialized: table` goes in the properties yml, and it does two jobs.
It caps the plan expansion that otherwise reaches into the `dim_students` CTAS
(see Risks), and it makes the model's own tests re-run on the data-change
automation condition, which only re-materializes tables.

The ordering has exactly two keys, and deliberately omits `rn_all`. See below.

### Why the ordering omits `rn_all`

The existing Tableau definition orders by `rn_all asc`. Do not copy it.

`rn_all` is itself `order by yearid desc, exitdate desc, reenrollments_dcid asc`
in PowerSchool and `academic_year desc, exitdate desc, startdate desc` in Focus.
As a sort key it therefore contributes exactly one thing beyond
`academic_year desc, exitdate desc`: a tiebreak when both of those tie. It
carries two defects while doing so.

It resolves ties by a different rule per source system — `reenrollments_dcid` in
PowerSchool, `startdate` in Focus.

It is region-scoped. PowerSchool computes it `partition by studentid`, so
ordering by `rn_all` across a `student_number` partition would interleave
independent rank sequences if a student ever held two `studentid` values.

The tiebreak is also unreachable.
`(student_number, school_level, academic_year, exitdate)` is unique across every
elementary and middle band row, so no two rows ever tie on both sort keys.
Neither sort column is ever null on that population, so the BigQuery NULLS-LAST
behaviour of `desc` cannot demote an active stint below a closed one.

That uniqueness is the invariant the two-key ordering depends on, and it is what
the determinism test below guards. It held identically across three separate
measurements while this design was written.

### `dim_students`

Add a `left join` on `student_number` and project both columns. The join must be
`left`: students who joined the network in high school legitimately have
neither, and they are null in the Tableau columns today too.

Both columns take `data_type: string` and `config.meta.contains_pii: true` in
`properties/dim_students.yml`.

The PII tag is not optional and the reasoning matters, because the obvious
argument for omitting it is wrong. 34 CFR 99.3 does name "most recent school
attended" as directory-information-eligible, but `.claude/rules/ferpa-pii.md`
forecloses that argument directly: designation is a policy act with parent
opt-out, not a property of the column, and absent confirmed KTAF designation the
default is to treat the field as PII. `school_level` on
`int_students__student_enrollments` already carries the tag. The tag changes no
access, because every `student-*` group on all four views uses
`member_level: { includes: "*" }`.

### Cube

Two dimensions on `src/cube/model/cubes/students/students.yml`, both
`public: true`. Then add both names to the `students` includes block and to the
Student folder on each of four views:

```text
views/student_assessments/student_assessment_scores_view.yml
views/students/student_attendance_enrollment_daily_view.yml
views/students/student_attendance_enrollment_periods_view.yml
views/students/student_section_enrollments_view.yml
```

Nothing else on the Cube side changes. No new cube, no new join, no
`access_policy` block, no `access.js` or `buildSecurityContext` change. The
`students` cube has zero joins, and all four views reach it with
`prefix: false`, so the member names and the folder entries are both bare.

The values are a location abbreviation held as degenerate text rather than a
`location_key` foreign key, and that choice needs an inline comment per the
diamond rule in `.claude/rules/cube-authoring.md`. A `students` to `locations`
join would give all four views a second path to `locations` alongside the
existing path through `student_school_enrollments`.

## Semantics the descriptions must state

The band comes from the **school**, not from the student's grade at the time.
`school_level` describes the school, and several KIPP schools serve grades
outside their designated band. Sumner, Royalty, Paterson Park Elementary and
Legacy Elementary are elementary-band and serve grade 5 or above. Hatch is
middle-band and serves grades 3 and 4.

The consequence is measurable. 339 students attended a KIPP school in a middle
grade and will read a null `most_recent_middle_school`. 332 students attended a
KIPP school in an elementary grade and will read a null
`most_recent_elementary_school`.

Null therefore covers three populations, not one:

1. The student has no stint at a school of that designated band.
2. The student attended those grades at a school of a different band.
3. The student has no enrollment record at all.

`dim_students` holds 31,244 rows and 26,517 receive a value, so 4,727 rows are
null. Only 2,234 of those are the high-school-only population.

Do not write "null means the student has no stint in that band." It is false for
339 students on the middle column and 332 on the elementary column, and both
counts grow as Sumner adds grades. Whether those two sets overlap was not
measured, so do not state a combined total.

This is not a regression the change introduces. The existing Tableau columns
carry the same property. `school_level_alt` patches Sumner alone, so it does not
address the others. A real fix belongs in `int_students__school_directory`,
which already sits at `(academic_year, region, ps_schoolid, grade_level)` grain
and already carries both `school_level` and `school_level_alt`. That is a
follow-up, not part of this change.

## Evidence

Every row was measured against prod before the design was accepted, on
2026-09-17.

Read the counts as point-in-time, not as invariants.
`int_students__student_enrollments` is a view, so each query reads current
upstream state: the middle-band row count came back as 42,573, then 42,572, then
42,571 across three reads an hour apart. The zero-valued rows are the claims
that matter, and each held at every read.

| Claim                                                                         | Result                        |
| ----------------------------------------------------------------------------- | ----------------------------- |
| Parity with live `es_attended` / `ms_attended` over 28,751 students           | 0 mismatches on either column |
| Students only in the new model                                                | 0                             |
| Students only in the extract (high-school-only and no-band)                   | 2,234                         |
| Band rows violating `(student_number, school_level, academic_year, exitdate)` | 0 of 92,579                   |
| Null `exitdate` or `academic_year` on band rows                               | 0 of 92,579                   |
| Students enrolled in more than one `_dbt_source_project`                      | 0 of 28,751                   |
| Rows with `grade_level = 99` carrying a non-null `school_level`               | 0 of 21,562                   |
| New-model rows with no matching `int_students__students` row                  | 0 of 26,517                   |

Regional coverage, students with a middle-band and elementary-band value:

| Region   | Middle | Elementary |
| -------- | -----: | ---------: |
| Camden   |  3,436 |      2,811 |
| Miami    |  1,927 |      2,508 |
| Newark   | 10,047 |     10,973 |
| Paterson |    327 |        716 |

Miami resolves because `int_focus__student_enrollment_roster.sql` coalesces
`school_level` to the crosswalk's `grade_band` for the two closed schools.
Exactly one Miami row carries a null `school_level`, and that row also carries a
null `school_abbreviation`, so both the new and the existing definition drop it.

The design assumes `student_number` is network-unique. Say so in the model
description, because the partition depends on it.

## Tests

`unique` on `student_number` on the new model. It is vacuous given the
`group by`, and `.claude/rules/dbt-models.md` requires a uniqueness test on
every intermediate regardless.

`dbt_utils.unique_combination_of_columns` on
`(student_number, school_level, academic_year, exitdate)`, in the model-level
`data_tests:` block of `properties/int_students__student_enrollments.yml`,
scoped with `config: where: "school_level in ('ES','MS')"`.

Three details about that second test. It cannot live on the new model, because
three of its four columns are not projected there. The scope matters: unscoped
it asserts the tuple over every row of the model, including high school,
out-of-district and graduate placeholders, none of which affect the pick, so a
failure would not mean what the test is for. Do not set `severity: warn`,
because kipptaf's `dbt_project.yml` already defaults every test to it.

Do not treat either uniqueness test as the fan-out tripwire for `dim_students`.
Both are `warn`. The `group by student_number` is what guarantees the grain.

## Pre-aggregation: leave both members out

`proficiency_rollup` on `student_assessment_scores.yml` lists `students.race`
and `students.gender_identity` and nothing else from `students`. A rollup serves
a query only when every grouped member is in it, so a school-attended cut falls
back to the fact. That is the accepted outcome, decided on measurement.

| Fallback query                                  | Elapsed | Slot time |  Bytes |
| ----------------------------------------------- | ------: | --------: | -----: |
| One academic year, `response_type = 'standard'` |   5.9 s |     104 s | 894 MB |
| All years, all response types, 14.98M rows in   |   6.3 s |     455 s | 591 MB |

Cube adds 0.9 to 1.5 seconds of its own overhead, so the worst case is about
eight seconds against the 55-second MCP poll deadline.

Both new members are one-to-one with the student, so adding them to the rollup
multiplies it against `race`, `gender_identity`, `grade_level`, `region_key`,
`abbreviation` and `module_code` to recover roughly two seconds. Document the
fallback in the member description instead.

One watch item: 455 slot-seconds on the broad cut is real compute if that query
runs often. It is not a reason to pre-aggregate, but it is worth knowing.

## Risks

**Plan expansion into a table mart.** `int_students__student_enrollments` is a
view that references 20 upstream relations, against 6 for
`int_students__students`, which is `dim_students`' only current input. BigQuery
inlines a view's SQL per reference, recursively, so without
`materialized: table` on the new model, every `dim_students` rebuild would
expand the whole enrollment view to compute two strings per student. Absolute
bytes are small, but the expansion is roughly 30x for a two-column add.
Materializing the new model caps it at one table read.

**ST06 on `dim_students.sql`.** That file already interleaves plain column refs
with function calls and carries no `trunk-ignore`, which means sqlfluff is
currently skipping the rule there, most likely the templated-slice effect
`.claude/rules/dbt-sql.md` warns about. Adding two plain refs can newly expose
it. Place them beside the other plain refs, then run
`.trunk/tools/trunk check --force --no-fix` on the file. If ST06 fires on
pre-existing lines, suppress rather than reorder a contracted column list.

**Duplication window.** `ms_attended` and `es_attended` keep their own inline
window until the follow-up lands, so the two definitions can drift. Put the
follow-up issue reference in an inline SQL comment at both derivation sites.
`.claude/rules/dbt-sql.md` carves out issue references and migration plumbing as
the one thing that belongs inline rather than in a `description`.

**Downstream consumers.** Re-run `grep -rn 'ref("dim_students")'` at
implementation time rather than trusting this line. Today the only SQL consumer
is `rpt_branchingminds__daily_attendance.sql`, which projects
`ds.lea_student_identifier` only, so the contract hazard for `select *`
consumers does not fire. No `select *` consumer of `dim_students` exists, and
`models/exposures/cube.yml` already lists the mart.

## Acceptance criteria

1. `uv run dbt build --select int_students__most_recent_schools_attended+ dim_students`
   passes.
2. A parity query returns 0 mismatches between the two new `dim_students`
   columns and the live `es_attended` and `ms_attended` values for all 28,751
   students.
3. All four student Cube views compile and return both new members, with
   row-level security unchanged for a region-scoped caller and a school-scoped
   caller.
4. `.trunk/tools/trunk check --force --no-fix` is clean on every touched SQL and
   YAML file.
5. Each member description states the pick rule, the
   school-band-not-student-grade caveat, and the three null populations.

## Out of scope

**High school attended.** Not requested, and for most students it is their
current school, already reachable through the enrollment join.

**`es_graduated`.** Produced by the same window with a different input, grade 4
with a June exit in the past, and consumed by `int_kippadb__roster`,
`int_kippadb__persistence` and `rpt_gsheets__kfwd_rem_roster`.

**A terminal-school-in-band variant.** `es_graduated` already approximates it if
the question returns.

## Follow-ups to file

1. Migrate `int_extracts__student_enrollments` to read the new model. The window
   feeds 11 call sites plus pass-throughs in
   `int_extracts__student_enrollments_subjects.sql`, `_subjects_weeks.sql`,
   `_weeks` and `int_extracts__course_enrollments_by_term`. It cannot retire the
   window entirely while `es_graduated` remains.
2. Fix the band-versus-grade gap in `int_students__school_directory`, covering
   Royalty, Paterson Park Elementary, Legacy Elementary and the Hatch direction,
   not Sumner alone.
3. Confirm with the requester whether the Cube cut is additive or replaces the
   existing one. `rpt_tableau__state_assessments_dashboard` and
   `rpt_tableau__college_assessment_dashboard_historic` already surface
   `ms_attended` on assessment dashboards.
