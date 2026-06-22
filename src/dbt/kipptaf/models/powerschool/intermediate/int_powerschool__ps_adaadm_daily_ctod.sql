with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__ps_adaadm_daily_ctod",
                    ),
                ]
            )
        }}
    ),

    calcs as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.student_number,
            mem.schoolid,
            mem.entrydate,
            mem.calendardate,
            mem.fteid,
            mem.attendance_conversion_id,
            mem.grade_level,
            mem.ontrack,
            mem.offtrack,
            mem.student_track,
            mem.yearid,
            mem.att_code,
            mem.attendancevalue,
            mem.potential_attendancevalue,
            mem.membershipvalue,

            t.academic_year,
            t.semester,
            t.term,

            cw.week_start_monday,
            cw.week_end_sunday,
            cw.week_number_academic_year,

            regexp_extract(
                mem._dbt_source_relation, r'(kipp\w+)_'
            ) as _dbt_source_project,

            abs(mem.attendancevalue - 1) as is_absent,

            if(
                mem.att_code like 'T%', 0.67, mem.attendancevalue
            ) as is_present_weighted,
            if(mem.att_code like 'T%', 1.0, 0.0) as is_tardy,
            if(mem.att_code like 'T%', 0.0, 1.0) as is_ontime,
            if(mem.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0) as is_oss,
            if(mem.att_code in ('S', 'ISS'), 1.0, 0.0) as is_iss,
            if(
                mem.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0
            ) as is_suspended,
            if(
                mem.att_code not in ('ISS', 'OSS', 'OS', 'OSSP', 'SHI'),
                abs(mem.attendancevalue - 1),
                0.0
            ) as is_absent_non_susp,

            -- A day that has actually occurred (<= today). The membership_reg
            -- calendar join emits a row for every in-session day in the
            -- enrollment span, including future year-end days; point-in-time
            -- anchors must ignore those or they latch onto the future last day
            -- of the year and collapse to zero once the fact filters to
            -- calendardate <= current_date.
            mem.calendardate
            <= current_date('{{ var("local_timezone") }}') as is_realized,

        from union_relations as mem
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on mem.yearid = t.yearid
            and mem.schoolid = t.schoolid
            and mem.calendardate between t.term_start_date and t.term_end_date
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="t") }}
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on mem.yearid = cw.yearid
            and mem.schoolid = cw.schoolid
            and mem.calendardate between cw.week_start_monday and cw.week_end_sunday
    ),

    anchors as (
        select
            *,

            -- Per-school point-in-time enrollment anchors. Drive the
            -- student_enrollments Cube. Anchored on the latest *realized* (past
            -- or today) in-session day per school so the as-of-now headcount
            -- can't collapse onto a future year-end row the fact filters out.
            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by schoolid, _dbt_source_project, academic_year
            ) as is_current_record,

            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by
                    schoolid,
                    _dbt_source_project,
                    academic_year,
                    date_trunc(calendardate, month)
            ) as is_enrollment_month_end_record,

            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by schoolid, _dbt_source_project, week_start_monday
            ) as is_enrollment_week_end_record,

            -- Per-stint attendance anchors. Drive the student_attendance Cube's
            -- latest / month-end / week-end CA snapshots. The stint is
            -- (student_number, _dbt_source_project, academic_year, entrydate) --
            -- the natural key behind student_enrollment_key in the fact. Latest
            -- is the stint's last realized day; month/week-end are its last
            -- realized *membership* day in the period.
            calendardate = max(if(is_realized, calendardate, null)) over (
                partition by
                    student_number, _dbt_source_project, academic_year, entrydate
            ) as is_latest_record,

            (
                calendardate
                = max(
                    if(is_realized and membershipvalue = 1, calendardate, null)
                ) over (
                    partition by
                        student_number,
                        _dbt_source_project,
                        academic_year,
                        entrydate,
                        date_trunc(calendardate, month)
                )
                and membershipvalue = 1
            ) as is_month_end_record,

            (
                calendardate
                = max(
                    if(is_realized and membershipvalue = 1, calendardate, null)
                ) over (
                    partition by
                        student_number,
                        _dbt_source_project,
                        academic_year,
                        entrydate,
                        week_start_monday
                )
                and membershipvalue = 1
            ) as is_week_end_record,

        from calcs
    ),

    running_calcs as (
        select
            *,

            sum(is_absent) over (
                partition by student_number, academic_year
                order by calendardate asc
                rows between 90 preceding and current row
            ) as n_absent_running_90,

            avg(is_absent) over (
                partition by academic_year, student_number order by calendardate asc
            ) as pct_absent_running_student_year,

            sum(membershipvalue) over (
                partition by academic_year, student_number
            ) as n_membership_student_year,

        from anchors
    )

select
    _dbt_source_relation,
    studentid,
    student_number,
    schoolid,
    entrydate,
    calendardate,
    fteid,
    attendance_conversion_id,
    grade_level,
    ontrack,
    offtrack,
    student_track,
    yearid,
    att_code,
    attendancevalue,
    potential_attendancevalue,
    membershipvalue,
    academic_year,
    semester,
    term,
    week_start_monday,
    week_end_sunday,
    week_number_academic_year,
    _dbt_source_project,
    is_absent,
    is_present_weighted,
    is_tardy,
    is_ontime,
    is_oss,
    is_iss,
    is_suspended,
    is_absent_non_susp,
    n_absent_running_90,
    pct_absent_running_student_year,
    n_membership_student_year,
    is_current_record,
    is_enrollment_month_end_record,
    is_enrollment_week_end_record,
    is_latest_record,
    is_month_end_record,
    is_week_end_record,

    pct_absent_running_student_year * n_membership_student_year as n_absent_projected,

    case
        when _dbt_source_project = 'kippmiami' and n_absent_running_90 >= 15
        then true
        when
            _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and pct_absent_running_student_year * n_membership_student_year >= 50
        then true
        else false
    end as is_truant,

from running_calcs
