with
    agg_weeks as (
        select
            _dbt_source_relation,
            studentid,
            schoolid,
            week_start_monday,
            week_end_sunday,

            yearid + 1990 as academic_year,
            sum(attendancevalue) as weekly_attendance_value,
            sum(membershipvalue) as weekly_membership_value,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where attendancevalue is not null
        group by
            _dbt_source_relation,
            studentid,
            yearid,
            schoolid,
            week_start_monday,
            week_end_sunday
    )

select
    _dbt_source_relation,
    studentid,
    schoolid,
    academic_year,
    week_start_monday,
    week_end_sunday,

    sum(weekly_attendance_value) over (
        partition by studentid, academic_year, schoolid order by week_start_monday
    ) as attendancevalue_running,
    sum(weekly_membership_value) over (
        partition by studentid, academic_year, schoolid order by week_start_monday
    ) as membershipvalue_running,
    round(
        safe_divide(
            sum(weekly_attendance_value) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday
            ),
            sum(weekly_membership_value) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday
            )
        ),
        3
    ) as ada_running,
from agg_weeks
