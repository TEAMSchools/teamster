# Enrollment week spines: exit-date boundary and one row per student-week

Issue: [#5504](https://github.com/TEAMSchools/teamster/issues/5504)

## Problem

The two weekly enrollment spines treat a stint's `exitdate` as an enrolled day.
That is right for Miami and wrong for NJ.

- **PowerSchool (Newark, Camden, Paterson):** `exitdate` is the first day the
  student is no longer enrolled.
- **Focus (Miami):** `int_focus__student_enrollment_roster` trims each stint to
  the day before the next stint starts, so `exitdate` is the last enrolled day.

As a result, an NJ stint that ends on a Monday is flagged `is_enrolled_week` for
that week. When the next stint starts the same Monday, the student looks
enrolled twice. The `_subjects_weeks` join also gives a stint a row for a week
whose only overlap is the exit date.

Separately, `int_topline__formative_assessment_weekly` filters on
`is_enrolled_week`, which drops every week a student entered after Monday.
Miami's first school week is hit hardest.

## Evidence that PowerSchool `exitdate` is exclusive

[#5386](https://github.com/TEAMSchools/teamster/pull/5386) (commit `74ec4774e3`)
concluded the opposite, from abutting stint pairs: 73,600 of 80,130 pairs had
`exitdate` one day before the next `entrydate`. That test cannot tell the two
readings apart. Measured 2026-09-23, 34,367 of the NJ pairs are the 1 July
rollover (exit 30 June, entry 1 July), and 30 June is not a school day under
either reading. Mid-year NJ handoffs split 70 equal against 96 one-day gaps.

Daily membership settles it. For NJ stints exiting outside June to August,
PowerSchool's `int_powerschool__ps_adaadm_daily_ctod` records the student's last
day with `membershipvalue > 0`:

| Measure                                               | Count |
| ----------------------------------------------------- | ----: |
| Mid-year NJ exits                                     | 4,777 |
| `exitdate` is an in-session day at that school        | 4,119 |
| Membership recorded on `exitdate`                     |     0 |
| Last membership day before `exitdate` (all with data) | 4,726 |

PowerSchool never counts a student as a member on the exit date, so this change
reverses `74ec4774e3` for PowerSchool. Miami keeps the inclusive reading.

Query, for a future re-check:

```sql
with
    stints as (
        select _dbt_source_project, student_number, schoolid, entrydate, exitdate,
        from `teamster-332318.kipptaf_extracts.int_extracts__student_enrollments`
        where
            _dbt_source_project != 'kippmiami'
            and grade_level != 99
            and extract(month from exitdate) not in (6, 7, 8)
            and exitdate > entrydate
    ),

    last_day as (
        select
            s.student_number,
            s.exitdate,

            max(m.calendardate) as last_member_day,
        from stints as s
        inner join
            `teamster-332318.kipptaf_powerschool.int_powerschool__ps_adaadm_daily_ctod`
            as m
            using (_dbt_source_project, student_number, schoolid, entrydate)
        where m.membershipvalue > 0
        group by s.student_number, s.exitdate
    )

select
    countif(last_member_day = exitdate) as member_on_exitdate,
    countif(last_member_day < exitdate) as last_member_before_exitdate,
from last_day
```

## Design

### 1. `last_enrolled_date`: one definition, at the SIS union

Add `last_enrolled_date`, the inclusive last enrolled day of a stint, in
`int_students__student_enrollments`, where the PowerSchool and Focus branches
meet. Each branch states its own convention:

- PowerSchool branch: `date_sub(exitdate, interval 1 day) as last_enrolled_date`
- Focus branch: `exitdate as last_enrolled_date`

There is no region `if`. The column reaches both spines through the existing
`select *` chain (`base_powerschool__student_enrollments`,
`int_extracts__student_enrollments`,
`int_extracts__student_enrollments_subjects`) and is added explicitly to
`_subjects_weeks`, which enumerates its columns.

`exitdate` keeps its meaning. `days_enrolled` and other `exitdate` uses outside
the spines are out of scope.

Edge cases, measured in prod:

- Every null `exitdate` is a grade-99 graduate placeholder (21,563 rows). The
  new column is null too, and those rows already never join to a week.
- There is no open-stint sentinel (`9999-12-31` or similar).
- NJ has no zero-day stints, so `last_enrolled_date` never falls before
  `entrydate`.
- Miami has 170 one-day stints (`entrydate = exitdate`) and 12 trimmed to
  nothing (`exitdate < entrydate`). The inclusive reading handles both: the
  former cover one day, the latter none.

The column gets a description in each properties yml it passes through, naming
both conventions and pointing at this spec for the membership evidence.

### 2. The spines

**`int_extracts__student_enrollments_subjects_weeks`** (view):

- `is_enrolled_week`:
  `week_start_monday between entrydate and last_enrolled_date`.
  `is_enrolled_week_end` is the same with `week_end_sunday`. `between` is
  correct because both ends are now inclusive and stints do not overlap.
- Week join: `co.last_enrolled_date >= cw.school_week_start_date` replaces
  `co.exitdate >= ...`. This drops PowerSchool rows whose only overlap with the
  week is the exit date.
- One row per student-week-discipline: `dbt_utils.deduplicate` with
  `partition_by="student_number, academic_year, week_start_monday, discipline"`
  and `order_by="is_enrolled_week desc, entrydate desc"`. That is the pick the
  four topline siblings already make, so their results change only by the flag
  fix. The partition omits `_dbt_source_project` as theirs does: a student who
  moves between regions mid-week gets one row.
- The grain test returns to the natural key (`student_number`, `academic_year`,
  `week_start_monday`, `discipline`) at `severity: error`.

This deliberately reverses #5386's per-stint grain. #5386 kept both stints of a
mid-week transfer to represent the double enrollment. In practice, 5 of the
model's 6 consumers pick one stint themselves, and the sixth,
`rpt_tableau__iready_apm`, joins lessons and weekly usage by student, subject
and week, not by stint dates. It gives both schools every lesson and the full
weekly totals, and its `rn_subject_week` tie-break across the two rows is
arbitrary. One school per week, the stint enrolled on Monday, is deterministic
and does not double-count. It affects 44 student-subject-weeks for 20 students
in AY2026. #5388, the upstream duplicate rows, is fixed, so the dedup chooses
between real stints and does not mask duplicate source rows.

**`int_extracts__student_enrollments_weeks`** (view): the same two flag changes.
Its join stays `academic_year` + `schoolid` with no date bound, because
attrition and enrollment denominators need rows for weeks after a student exits.
Its dedup order becomes `is_enrolled_week desc, entrydate desc`, which makes the
pick deterministic when neither stint is flagged.

### 3. Consumers

Code changes:

- `int_topline__iready_diagnostic_weekly`, `int_topline__iready_lessons_weekly`,
  `int_topline__state_assessments_weekly`,
  `int_topline__star_assessment_weekly`: delete the `subject_weeks_deduplicate`
  CTE and read `subject_weeks`, which keeps its column list and filter.
- `int_topline__formative_assessment_weekly`: delete the `sw.is_enrolled_week`
  filter. The spine already has one row per student-week. The post-join
  `formative_strategy` dedup and the grain test stay.
- `rpt_tableau__student_attrition_over_time`:
  `if(co.is_enrolled_week, 0, 1) as is_attrition`, reusing the corrected flag
  instead of repeating the date check. For an NJ stint that exits on a Monday,
  the student now counts as attrited that week, not the following week.

No code change, values shift for NJ: `rpt_gsheets__school_metrics_extract`,
`rpt_tableau__ddi_dashboard` (uses `is_enrolled_week_end`),
`rpt_tableau__okrts_behavior`, `rpt_tableau__iready_apm`,
`int_topline__attendance_contacts`, `int_topline__attendance_contacts_weekly`,
`int_topline__attendance_interventions_weekly`,
`int_topline__college_entrance_exams_weekly`,
`int_topline__college_matriculation_weekly`,
`int_topline__deanslist_incentives_weekly`,
`int_topline__gpa_cumulative_weekly`, `int_topline__gpa_term_weekly`,
`int_topline__student_metrics`. The biggest visible effect is "Total Enrollment"
in `int_topline__student_metrics`, which stops counting an NJ student in a week
whose Monday is their exit date.

## Testing

One dbt unit test on `int_extracts__student_enrollments_subjects_weeks`, three
cases:

1. NJ Monday handoff: stint A exits Monday, stint B enters the same Monday.
   Expect one row for that week, stint B, `is_enrolled_week` true.
2. NJ stint whose `exitdate` is the week's first in-session day. Expect no row
   for that week.
3. Miami stint whose `exitdate` is a Monday. Expect a row, flagged.

## Validation

Compare main's compiled SQL with the branch's against the same prod data:

| Check (AY2025+)                                          | Before | After |
| -------------------------------------------------------- | -----: | ----: |
| NJ rows, `exitdate = week_start_monday`, flagged         |    206 |     0 |
| PowerSchool rows, `exitdate = school_week_start_date`    |    296 |     0 |
| `_subjects_weeks` duplicate student-week-discipline keys |     74 |     0 |
| ...with both stints flagged                              |      6 |     0 |

- Formative: every existing key kept, new keys all mid-week-entry weeks (about
  7,000: Miami 5,516, Newark 954, Camden 456, Paterson 108 before the boundary
  fix), no value change on existing keys.
- The four sibling toplines: row diff against main, expected only at NJ boundary
  weeks.
- Attrition and Total Enrollment: before/after counts per region, reported in
  the PR body.
- `uv run dbt build` of the changed models and all consumers listed above with
  `--defer`, every grain test passing.

## Rollout

No DDL and no backfill. The views change on deploy. The tables
(`int_extracts__student_enrollments`, the topline models) rebuild through
Dagster on the code-version change.

## Out of scope

- `exitdate` semantics anywhere else, including `days_enrolled`.
- Attributing a transfer week's lessons to each stint by date in
  `rpt_tableau__iready_apm`.
- Restructuring the two spines onto a shared stint-week parent.
