with
    agg_weeks as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday,

            sum(is_absent) as absence_sum,
            sum(attendancevalue) as attendance_value_sum,
            sum(membershipvalue) as membership_value_sum,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            attendancevalue is not null
            and calendardate < current_date('{{ var("local_timezone") }}')
        group by
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday
    ),

    running_calcs as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            academic_year,
            week_start_monday,
            week_end_sunday,
            absence_sum,
            attendance_value_sum,
            membership_value_sum,

            sum(absence_sum) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday asc
            ) as absence_sum_running,

            sum(attendance_value_sum) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday asc
            ) as attendance_value_sum_running,

            sum(membership_value_sum) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday asc
            ) as membership_value_sum_running,
        from agg_weeks
    )

select
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.school,
    co.studentid,
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.grade_level,
    co.gender,
    co.ethnicity,
    co.iep_status,
    co.is_504,
    co.lep_status,
    co.gifted_and_talented,
    co.entrydate,
    co.exitdate,
    co.enroll_status,
    co.week_start_monday,
    co.week_end_sunday,

    sum(agg.absence_sum) over (
        partition by co.studentid, co.academic_year, co.schoolid
        order by co.week_start_monday asc
    ) as absence_sum_running,

    sum(agg.attendance_value_sum) over (
        partition by co.studentid, co.academic_year, co.schoolid
        order by co.week_start_monday asc
    ) as attendance_value_sum_running,

    sum(agg.membership_value_sum) over (
        partition by co.studentid, co.academic_year, co.schoolid
        order by co.week_start_monday asc
    ) as membership_value_sum_running,

    round(
        safe_divide(
            sum(agg.attendance_value_sum) over (
                partition by co.studentid, co.academic_year, co.schoolid
                order by co.week_start_monday asc
            ),
            sum(agg.membership_value_sum) over (
                partition by co.studentid, co.academic_year, co.schoolid
                order by co.week_start_monday asc
            )
        ),
        3
    ) as ada_running,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    agg_weeks as agg
    on co.studentid = agg.studentid
    and co.schoolid = agg.schoolid
    and co.academic_year = agg.academic_year
    and co.week_start_monday = agg.week_start_monday
where co.academic_year >= {{ var("current_academic_year") - 1 }}
