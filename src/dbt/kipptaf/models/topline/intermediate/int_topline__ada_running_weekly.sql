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
        where attendancevalue is not null
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

    rc.week_start_monday,
    rc.week_end_sunday,
    rc.attendance_value_sum,
    rc.membership_value_sum,
    rc.absence_sum_running,
    rc.attendance_value_sum_running,
    rc.membership_value_sum_running,

    round(
        safe_divide(attendance_value_sum_running, membership_value_sum_running), 3
    ) as ada_running,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    running_calcs as rc
    on co.studentid = rc.studentid
    and co.schoolid = rc.schoolid
    and co.academic_year = rc.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="rc") }}
where co.academic_year >= {{ var("current_academic_year") - 1 }}
