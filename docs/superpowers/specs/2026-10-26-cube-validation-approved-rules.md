# Cube validation: rules carried over from the first tool

Appendix to the Cube validation and build skill design (#6150). The first
validation tool and its branch are deleted. This file keeps what the analyst
approved during its runs, because those calls cannot be rebuilt from code.

Treat every rule here as a starting point, not a verdict. Each was measured on a
capture whose timing the new design replaces, so the new tool re-measures each
one before relying on it.

## Analyst decisions

Attendance (approved 2026-10-20 unless noted):

- Chronic absence counts students who transferred out.
- Truancy counts each student once, as of their own last day.
- Attendance code `TD` is a tardy.
- Cube keeps the Focus exit date, inclusive.
- Miami same-day exits (mostly first-day no-shows) stay in Cube, because the
  dashboard counts them. This raises Miami AY2026 chronic absence.
- `count_students` is the enrollment headcount; `count_students_measured` is the
  rate denominator (#6059 option A). Ops wants enrollment that does not depend
  on attendance being marked.
- A measure reused across tabs with the same calculation inherits its verdict.
- Fixes consolidate: 1 Asana task for dashboard fixes, 1 GitHub issue for Cube
  fixes.

Assessments:

- Cube stays internal-only for Illuminate. An untagged assessment is a tagging
  cause owned by the source; tagging is ongoing.
- DDI Module % Completion is an accepted difference: Focus rows with no score,
  and Cube documents no participation rate for Focus.
- One review issue per domain goes to the domain owner, posted only on the
  analyst's OK.
- No production refresh to make a comparison possible.

## Open questions for domain owners

- APM retakes: which sitting counts?
- DDI teacher: is the teacher shown the section's lead teacher or the course
  teacher?
- Attendance Tracker "Enroll Status 2": which Cube enrollment status matches the
  extract's code 2? Cube's `Transferred Out` picks different students.
- `# OSS`: should code `SHI` count as an out-of-school suspension? Cube says
  yes; the workbook says no.
- Is the Attendance Dashboard's Miami - NSLP tab still in use? Its defaults sit
  on AY2023 and AY2024.

## Known challenges to these rules

From the 2026-10-26 review of the first tool. Verified means re-counted on the
snapshot; reported means not yet re-checked.

- Verified: `no-resolved-section` (DDI Assessment) claimed 369 rows on 6
  assessments its resolver table never held, so the rule had no evidence for
  them.
- Verified: `assessment-filed-in-another-year` claims any value difference on a
  mismatched year. All 1,673 rows it claimed differed in grade level only.
- Verified: 696 dashboard-only rows on 1 tagged assessment stayed unexplained on
  DDI Assessment. It is the strongest candidate for a real Cube gap.
- Reported: the chronic, truant and on-time dashboard-fix decisions rest only on
  probes run before #6066 changed the fact.
- Reported: APM `retake` names the dashboard as owner while its domain-owner
  question is still open.

## Rules by checks file

Each block is the file's `causes`, `decisions`, `questions`, `probes` and
`must_cover` as last saved. `where` and probe SQL use the first tool's row
columns (`base`, `k_*`, `t_*`, `c_*`, `d_*`), so they need translating to the
new tool's names.

### `apm.yml`

Dashboard `apm`.

```yaml
causes:
  - id: grades-9-12-not-in-apm
    description:
      APM's model keeps grades K to 8 (rpt_tableau__iready_apm filters
      grade_level <= 8); Cube keeps high-school diagnostics.
    where: base = 'cube_only' and c_grade_level >= 9
    owner: dashboard
  - id: weeks-without-a-diagnostic
    description:
      The extract keeps a weekly row for students with no diagnostic yet (no
      test round, no score); Cube has no score row to match.
    where: base = 'dashboard_only' and t_test_round is null
    owner: dashboard
  - id: outside-round
    description:
      Cube keeps i-Ready diagnostics taken outside the BOY, MOY and EOY windows;
      APM shows only the window rounds.
    where:
      base = 'cube_only' and c_administration_period = 'Outside Round' and
      coalesce(c_grade_level < 9, true)
    owner: dashboard
  - id: retake
    description:
      A student sat the same round twice; Cube keeps every sitting and APM shows
      1. Which sitting counts is an open decision in Cube's guidance.
    where:
      base = 'cube_only' and c__dup > 1 and c_administration_period is distinct
      from 'Outside Round' and coalesce(c_grade_level < 9, true)
    owner: dashboard
questions:
  - "When a student sits the same i-Ready round twice, which sitting should
    count: the first, the latest, or the higher score? APM shows 1 sitting and
    Cube keeps both."
```

### `attendance_dashboard (rehearsal).yml`

Dashboard `attendance_dashboard`.

```yaml
causes:
  - id: not-a-membership-day
    description:
      Cube carries a row for every calendar day a student is enrolled, weekends
      and breaks included; the extract carries membership days only.
    where: base = 'cube_only' and coalesce(c_membership_value, 0) = 0
    owner: cube
    inert: true
  - id: no-attendance-value
    description:
      Cube has a membership day whose attendance value is null, sometimes with
      an attendance code already entered; the extract has no row for it.
    where:
      base = 'cube_only' and c_membership_value > 0 and c_attendance_value is
      null
    owner: source
    inert: true
  - id: exit-day-counted
    description:
      "Miami: the extract counts the enrollment's exit date as a membership day;
      Cube's rows end the calendar day before."
    where:
      base = 'dashboard_only' and l_region = 'Miami' and exists (select 1 from
      rows_base c where c.in_c and c.k_student = rows_base.k_student and
      c.k_school = rows_base.k_school and c.k_day = rows_base.k_day - 1)
    owner: cube
  - id: same-day-exit
    description:
      "Miami: an enrollment that exits on its entry date. The extract counts
      that day; Cube has no row for it."
    where:
      base = 'dashboard_only' and l_region = 'Miami' and not exists (select 1
      from rows_base c where c.in_c and c.k_student = rows_base.k_student and
      c.k_school = rows_base.k_school and c.k_day between rows_base.k_day - 1
      and rows_base.k_day + 1)
    owner: cube
decisions:
  - measure: Avg. Attendance Metric
    param:
      Attendance Metric: Chronic Absenteeism
    owner: dashboard
    rule:
      The dashboard leaves out current-year students who have since transferred
      out (enroll_status 2); Cube counts every student served in the slice.
    probe: chronic-keeps-transfers
    task: https://app.asana.com/0/0/1219715197150814
  - measure: Avg. Attendance Metric
    param:
      Attendance Metric: Truant/On Track for Truancy
    owner: dashboard
    rule:
      The dashboard weights each student by their days in the mark and counts
      only students enrolled on the extract's last date; Cube counts each
      student once, as of their own last day.
    probe: truant-per-student
    task: https://app.asana.com/0/0/1219715197150814
  - measure: Avg. Attendance Metric
    param:
      Attendance Metric: \% On-Time
    owner: dashboard
    rule:
      The dashboard's Tardy group leaves out code TD; Cube's is_tardy counts
      every T code.
    probe: ontime-tardy-codes
    task: https://app.asana.com/0/0/1219715197150814
probes:
  - id: chronic-keeps-transfers
    measure: Avg. Attendance Metric
    param:
      Attendance Metric: Chronic Absenteeism
    dashboard:
      select avg(case when ada_running is null then null when academic_year =
      2026 and enroll_status = 2 then null when ada_running <= 0.9 then 1.0 else
      0.0 end) from (select *, max(calendardate) over (partition by
      student_number, academic_year) as mx from {extract} where {where}) z where
      calendardate = mx
    candidate:
      select avg(case when ada_running is null then null when ada_running <= 0.9
      then 1.0 else 0.0 end) from (select *, max(calendardate) over (partition
      by student_number, academic_year) as mx from {extract} where {where}) z
      where calendardate = mx
  - id: truant-per-student
    measure: Avg. Attendance Metric
    param:
      Attendance Metric: Truant/On Track for Truancy
    dashboard:
      select avg(flag) from (select *, max(case when calendardate = gmax and
      enroll_status = 0 then case when is_truant then 1.0 else 0.0 end end) over
      (partition by student_number, academic_year) as flag from (select *,
      max(calendardate) over () as gmax from {extract}) a) b where {where}
    candidate:
      select avg(case when is_truant then 1.0 else 0.0 end) from (select *,
      max(calendardate) over (partition by student_number, academic_year) as mx
      from {extract} where {where}) z where calendardate = mx
  - id: ada-full-membership
    measure: Avg. Attendance Metric
    dashboard: select avg(is_present) from {extract} where {where}
    candidate:
      select sum(case when membershipvalue = 1 then is_present end) /
      nullif(sum(case when membershipvalue = 1 and is_present is not null then
      1.0 end), 0) from {extract} where {where}
  - id: ontime-tardy-codes
    measure: Avg. Attendance Metric
    param:
      Attendance Metric: \% On-Time
    dashboard:
      select avg(case when is_present = 0 then null when att_code in ('ET', 'T',
      'T10', 'TLE') then 0.0 else 1.0 end) from {extract} where {where}
    candidate:
      select 1 - sum(case when membershipvalue = 1 and is_present is not null
      then is_tardy else 0 end) / nullif(sum(case when membershipvalue = 1 and
      is_absent = 0 then 1.0 else 0 end), 0) from {extract} where {where}
must_cover:
  - name: ADA
    source: https://app.asana.com/0/0/1214075610424640
    cube:
      member: avg_daily_attendance
      view: student_attendance_enrollment_daily_view
    tableau:
      column: Avg. Attendance Metric
  - name: "% On-Time"
    source: https://app.asana.com/0/0/1219087795895880
    cube:
      member: pct_ontime
      view: student_attendance_enrollment_daily_view
    tableau:
      column: Avg. Attendance Metric
      param:
        Attendance Metric: \% On-Time
  - name: Chronic Absenteeism
    source: https://app.asana.com/0/0/1219288661376295
    cube:
      member: pct_chronically_absent
      view: student_attendance_enrollment_periods_view
    tableau:
      column: Avg. Attendance Metric
      param:
        Attendance Metric: Chronic Absenteeism
  - name: "% Truant"
    source: https://app.asana.com/0/0/1214073491303422
    cube:
      member: pct_truant
      view: student_attendance_enrollment_periods_view
    tableau:
      column: Avg. Attendance Metric
      param:
        Attendance Metric: Truant/On Track for Truancy
  - name: CountD Student Number
    source: https://app.asana.com/0/0/1219285655850612
    cube:
      member: count_students
      view: student_attendance_enrollment_daily_view
    tableau:
      column: Distinct count of Student Number
  - name: "# Tardy"
    source: https://app.asana.com/0/0/1214703929266204
    cube:
      member: count_tardy_days
      view: student_attendance_enrollment_daily_view
    tableau:
      column: "# Tardy"
  - name: "# Absences"
    source: https://app.asana.com/0/0/1219285941351457
    cube:
      member: count_absent_days
      view: student_attendance_enrollment_daily_view
    tableau:
      column: "# Absences"
  - name: Membershipvalue
    source: https://app.asana.com/0/0/1219285583802448
    cube: null
    tableau:
      column: Membershipvalue
    rows:
      - membership_value
  - name: "# ISS / # OSS"
    source: https://app.asana.com/0/0/1219285741164120
    cube: null
    tableau:
      column: "# ISS"
    rows:
      - is_iss
      - is_oss
  - name: "# Present"
    source: https://app.asana.com/0/0/1219285741352984
    cube: null
    tableau:
      column: "# Present"
    rows:
      - attendance_value
  - name: Is Absent Weighted
    source: https://app.asana.com/0/0/1219285741178319
    cube: null
    tableau:
      column: Is Absent Weighted
    rows:
      - is_absent
      - is_tardy
  - name: Attendance Pts
    source: https://app.asana.com/0/0/1219285741180458
    cube: null
    tableau:
      column: Attendance Pts
    rows:
      - attendance_code
  - name: Days to 90%
    source: https://app.asana.com/0/0/1219285741025130
    cube: null
    tableau:
      column: Days to 90%
    rows:
      - membership_value
      - is_absent
  - name: "# Abs by Student, 90-day rolling"
    source: https://app.asana.com/0/0/1219285988841219
    cube: null
    tableau:
      column: "# Abs by Student - LOD Miami Truancy"
    rows:
      - is_absent
```

### `attendance_dashboard.yml`

Dashboard `attendance_dashboard`.

```yaml
causes:
  - id: not-a-membership-day
    description:
      Cube keeps every enrolled day; the dashboard keeps only days with
      membership 1 and a recorded attendance value.
    where:
      base = 'cube_only' and (c_membership_value <> 1 or c_attendance_value is
      null)
    owner: dashboard
    inert: true
  - id: no-cube-rows-for-student
    description:
      The dashboard has days for a student who has no Cube rows anywhere in the
      period.
    where:
      base = 'dashboard_only' and not exists (select 1 from rows_base c where
      c.in_c and c."k_student" = rows_base."k_student")
    owner: undecided
  - id: after-last-cube-day
    description:
      The dashboard has a day after the student's last Cube day at that school.
    where:
      base = 'dashboard_only' and "k_day" > (select max(c."k_day") from
      rows_base c where c.in_c and c."k_student" = rows_base."k_student" and
      c."k_school" = rows_base."k_school")
    owner: undecided
```

### `ddi_suite_assessment.yml`

Dashboard `ddi_suite_assessment`.

```yaml
causes:
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and x.canonical_assessment_id =
      cast(rows_base.k_assessment as bigint)) and not exists (select 1 from
      "tags"."extra"."rows" y where y.assessment_id =
      cast(rows_base.k_assessment as bigint) and not y.is_internal)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and x.canonical_assessment_id = cast(rows_base.k_assessment as bigint) and
      not x.has_school_enrollment)
    owner: cube
  - id: assessment-filed-in-another-year
    description:
      The extract files the assessment under a different academic year than its
      date (the first case is last year's assessment given this year), so it
      labels the score with that year's grade; Cube files it by date.
    where:
      base = 'value_differs' and t_academic_year is distinct from
      cast(c_academic_year as bigint)
    owner: source
  - id: grade-changed-mid-year
    description:
      The student moved grades during the year. The extract labels every score
      with the current grade; Cube uses the grade of the enrollment the score
      falls in. Scores agree; only the grade label differs.
    where:
      base = 'value_differs' and d_grade_level and not d_percent_correct and not
      d_is_mastery and not d_performance_band and t_academic_year =
      cast(c_academic_year as bigint)
    owner: dashboard
  - id: untagged-assessment
    description:
      The assessment has no AppSheet tag, so Cube's star leaves it out by
      design; tagging is ongoing, and a tagged assessment flows into Cube by
      itself.
    where:
      base = 'dashboard_only' and exists (select 1 from "tags"."extra"."rows" x
      where x.assessment_id = cast(rows_base.k_assessment as bigint) and not
      x.is_internal)
    owner: source
questions:
  - Is the teacher DDI shows for a section the section's lead teacher? If so,
    Cube's lead-teacher members can back the Teacher sheet.
```

### `ddi_suite_dki.yml`

Dashboard `ddi_suite_dki`.

```yaml
causes:
  - id: grade-changed-mid-year
    description:
      The student moved grades during the year. The extract labels every score
      with the current grade; Cube uses the grade of the enrollment the score
      falls in. Scores agree; only the grade label differs.
    where:
      base = 'value_differs' and d_grade_level and not d_percent_correct and not
      d_is_mastery and not d_performance_band and not d_is_complete
    owner: dashboard
  - id: wpp-dropped-by-extract
    description:
      Cube keeps WPP module rows; the DDI extract drops them
      (rpt_tableau__ddi_dashboard filters module_type != 'WPP').
    where: base = 'cube_only' and c_module_type = 'WPP'
    owner: dashboard
  - id: walkthrough-rows
    description:
      The extract's walkthrough rows are staff observations, a second source
      with no assessment-score counterpart in Cube.
    where: base = 'dashboard_only' and t_response_type = 'walkthrough'
    owner: dashboard
  - id: assessment-absent-from-extract
    description:
      Cube has scores for an assessment the extract carries no row for at all;
      the first case was last year's assessment dated in this year, which the
      extract's school weeks never pick up.
    where:
      base = 'cube_only' and c_module_type is distinct from 'WPP' and not exists
      (select 1 from rows_base r where r.in_t and r.k_assessment =
      rows_base.k_assessment)
    owner: source
  - id: before-first-school-week
    description:
      Cube keeps a score dated before the school's first school week of that
      academic year; the extract builds its rows from school weeks.
    where:
      base = 'cube_only' and exists (select 1 from rows_base r where r.in_t and
      r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year") and not exists (select 1 from rows_base r
      where r.in_t and r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year" and cast(r."t_week_start_monday" as date) <=
      rows_base.k_day)
    owner: dashboard
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and cast(x.canonical_assessment_id
      as text) = rows_base.k_assessment)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and cast(x.canonical_assessment_id as text) = rows_base.k_assessment and
      not x.has_school_enrollment)
    owner: cube
```

### `ddi_suite_module.yml`

Dashboard `ddi_suite_module`.

```yaml
causes:
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and x.canonical_assessment_id =
      cast(rows_base.k_assessment as bigint)) and not exists (select 1 from
      "tags"."extra"."rows" y where y.assessment_id =
      cast(rows_base.k_assessment as bigint) and not y.is_internal)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and x.canonical_assessment_id = cast(rows_base.k_assessment as bigint) and
      not x.has_school_enrollment)
    owner: cube
  - id: assessment-filed-in-another-year
    description:
      The extract files the assessment under a different academic year than its
      date (the first case is last year's assessment given this year), so it
      labels the score with that year's grade; Cube files it by date.
    where:
      base = 'value_differs' and t_academic_year is distinct from
      cast(c_academic_year as bigint)
    owner: source
  - id: grade-changed-mid-year
    description:
      The student moved grades during the year. The extract labels every score
      with the current grade; Cube uses the grade of the enrollment the score
      falls in. Scores agree; only the grade label differs.
    where:
      base = 'value_differs' and d_grade_level and not d_percent_correct and not
      d_is_mastery and not d_performance_band and t_academic_year =
      cast(c_academic_year as bigint)
    owner: dashboard
  - id: untagged-assessment
    description:
      The assessment has no AppSheet tag, so Cube's star leaves it out by
      design; tagging is ongoing, and a tagged assessment flows into Cube by
      itself.
    where:
      base = 'dashboard_only' and exists (select 1 from "tags"."extra"."rows" x
      where x.assessment_id = cast(rows_base.k_assessment as bigint) and not
      x.is_internal)
    owner: source
decisions:
  - measure: Avg. % Completion
    owner: accepted
    rule:
      Focus Assessments rows with no score read not complete on the dashboard
      and taken in Cube, which documents no participation rate for Focus.
    sheets:
      - Module - Overall - Summary
    task: ""
  - measure: Avg. % Completion
    owner: accepted
    rule:
      Focus Assessments rows with no score read not complete on the dashboard
      and taken in Cube, which documents no participation rate for Focus.
    cuts:
      - param-dashboard-view-assessments-over-time
      - param-assessments-over-time-grade-level
      - param-assessments-over-time-iep-status
      - param-assessments-over-time-module-type
    task: ""
```

### `ddi_suite_mot_region.yml`

Dashboard `ddi_suite_mot_region`.

```yaml
causes:
  - id: wpp-dropped-by-extract
    description:
      Cube keeps WPP module rows; the DDI extract drops them
      (rpt_tableau__ddi_dashboard filters module_type != 'WPP').
    where: base = 'cube_only' and c_module_type = 'WPP'
    owner: dashboard
  - id: walkthrough-rows
    description:
      The extract's walkthrough rows are staff observations, a second source
      with no assessment-score counterpart in Cube.
    where: base = 'dashboard_only' and t_response_type = 'walkthrough'
    owner: dashboard
  - id: assessment-absent-from-extract
    description:
      Cube has scores for an assessment the extract carries no row for at all;
      the first case was last year's assessment dated in this year, which the
      extract's school weeks never pick up.
    where:
      base = 'cube_only' and c_module_type is distinct from 'WPP' and not exists
      (select 1 from rows_base r where r.in_t and r.k_assessment =
      rows_base.k_assessment)
    owner: source
  - id: before-first-school-week
    description:
      Cube keeps a score dated before the school's first school week of that
      academic year; the extract builds its rows from school weeks.
    where:
      base = 'cube_only' and exists (select 1 from rows_base r where r.in_t and
      r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year") and not exists (select 1 from rows_base r
      where r.in_t and r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year" and cast(r."t_week_start_monday" as date) <=
      rows_base.k_day)
    owner: dashboard
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and cast(x.canonical_assessment_id
      as text) = rows_base.k_assessment)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and cast(x.canonical_assessment_id as text) = rows_base.k_assessment and
      not x.has_school_enrollment)
    owner: cube
```

### `ddi_suite_mot_school.yml`

Dashboard `ddi_suite_mot_school`.

```yaml
causes:
  - id: wpp-dropped-by-extract
    description:
      Cube keeps WPP module rows; the DDI extract drops them
      (rpt_tableau__ddi_dashboard filters module_type != 'WPP').
    where: base = 'cube_only' and c_module_type = 'WPP'
    owner: dashboard
  - id: walkthrough-rows
    description:
      The extract's walkthrough rows are staff observations, a second source
      with no assessment-score counterpart in Cube.
    where: base = 'dashboard_only' and t_response_type = 'walkthrough'
    owner: dashboard
  - id: assessment-absent-from-extract
    description:
      Cube has scores for an assessment the extract carries no row for at all;
      the first case was last year's assessment dated in this year, which the
      extract's school weeks never pick up.
    where:
      base = 'cube_only' and c_module_type is distinct from 'WPP' and not exists
      (select 1 from rows_base r where r.in_t and r.k_assessment =
      rows_base.k_assessment)
    owner: source
  - id: before-first-school-week
    description:
      Cube keeps a score dated before the school's first school week of that
      academic year; the extract builds its rows from school weeks.
    where:
      base = 'cube_only' and exists (select 1 from rows_base r where r.in_t and
      r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year") and not exists (select 1 from rows_base r
      where r.in_t and r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year" and cast(r."t_week_start_monday" as date) <=
      rows_base.k_day)
    owner: dashboard
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and cast(x.canonical_assessment_id
      as text) = rows_base.k_assessment)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and cast(x.canonical_assessment_id as text) = rows_base.k_assessment and
      not x.has_school_enrollment)
    owner: cube
```

### `ddi_suite_o3.yml`

Dashboard `ddi_suite_o3`.

```yaml
causes:
  - id: wpp-dropped-by-extract
    description:
      Cube keeps WPP module rows; the DDI extract drops them
      (rpt_tableau__ddi_dashboard filters module_type != 'WPP').
    where: base = 'cube_only' and c_module_type = 'WPP'
    owner: dashboard
  - id: walkthrough-rows
    description:
      The extract's walkthrough rows are staff observations, a second source
      with no assessment-score counterpart in Cube.
    where: base = 'dashboard_only' and t_response_type = 'walkthrough'
    owner: dashboard
  - id: assessment-absent-from-extract
    description:
      Cube has scores for an assessment the extract carries no row for at all;
      the first case was last year's assessment dated in this year, which the
      extract's school weeks never pick up.
    where:
      base = 'cube_only' and c_module_type is distinct from 'WPP' and not exists
      (select 1 from rows_base r where r.in_t and r.k_assessment =
      rows_base.k_assessment)
    owner: source
  - id: before-first-school-week
    description:
      Cube keeps a score dated before the school's first school week of that
      academic year; the extract builds its rows from school weeks.
    where:
      base = 'cube_only' and exists (select 1 from rows_base r where r.in_t and
      r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year") and not exists (select 1 from rows_base r
      where r.in_t and r.k_school = rows_base.k_school and r."t_academic_year" =
      rows_base."c_academic_year" and cast(r."t_week_start_monday" as date) <=
      rows_base.k_day)
    owner: dashboard
  - id: no-resolved-section
    description:
      The scores fact's section resolver placed no section for the student's
      score on this assessment, so Cube drops it by design.
    where:
      base = 'dashboard_only' and t_response_type is distinct from 'walkthrough'
      and not exists (select 1 from "resolver"."extra"."rows" x where
      x.student_number = rows_base.k_student and cast(x.canonical_assessment_id
      as text) = rows_base.k_assessment)
    owner: cube
  - id: orphan-section-enrollment
    description:
      The resolver placed the score in a section enrollment whose school
      enrollment is missing, so Cube's view has no school for it and row-level
      security hides the score.
    where:
      base = 'dashboard_only' and exists (select 1 from
      "resolver"."extra"."rows" x where x.student_number = rows_base.k_student
      and cast(x.canonical_assessment_id as text) = rows_base.k_assessment and
      not x.has_school_enrollment)
    owner: cube
```

### `literacy.yml`

Dashboard `literacy`.

```yaml
causes:
  - id: progress-monitoring-rows
    description:
      Progress-monitoring scores; Cube has no progress-monitoring rows (the
      Asana PM measures are mart-ready, not in Cube).
    where: base = 'dashboard_only' and t_assessment_type = 'PM'
    owner: cube
  - id: benchmark-not-taken
    description:
      The extract's scaffold row for a benchmark the student has not taken (no
      date, no score); Cube has no score row to match.
    where:
      base = 'dashboard_only' and t_assessment_type = 'Benchmark' and
      t_client_date is null
    owner: dashboard
```

### `stat.yml`

Dashboard `stat`.

No causes, decisions, questions or probes recorded.

### `attendance_dashboard_student_attendance_tracker.yml`

Dashboard `attendance_dashboard_student_attendance_tracker`.

No causes, decisions, questions or probes recorded.

### `attendance_dashboard_ay2025.yml`

Dashboard `attendance_dashboard_ay2025`.

```yaml
causes:
  - id: not-a-membership-day
    description:
      Cube keeps every enrolled day; the dashboard keeps only days with
      membership 1 and a recorded attendance value.
    where:
      base = 'cube_only' and (c_membership_value <> 1 or c_attendance_value is
      null)
    owner: dashboard
    inert: true
  - id: no-cube-rows-for-student
    description:
      The dashboard has days for a student who has no Cube rows anywhere in the
      period.
    where:
      base = 'dashboard_only' and not exists (select 1 from rows_base c where
      c.in_c and c."k_student" = rows_base."k_student")
    owner: undecided
  - id: after-last-cube-day
    description:
      The dashboard has a day after the student's last Cube day at that school.
    where:
      base = 'dashboard_only' and "k_day" > (select max(c."k_day") from
      rows_base c where c.in_c and c."k_student" = rows_base."k_student" and
      c."k_school" = rows_base."k_school")
    owner: undecided
```
