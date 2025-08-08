with
    agg_weeks as (
        select
            studentid,
            yearid,
            schoolid,
            week_start_monday,

            sum(attendancevalue) as weekly_attendance_value,
            sum(membershipvalue) as weekly_membership_value
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where attendancevalue is not null
        group by studentid, yearid, schoolid, week_start_monday
    )

select
    studentid,
    yearid,
    week_start_monday,

    sum(weekly_attendance_value) over (
        partition by studentid, yearid order by week_start_monday
    ) as attendancevalue_running,
    sum(weekly_membership_value) over (
        partition by studentid, yearid order by week_start_monday
    ) as membershipvalue_running,
    safe_divide(
        sum(weekly_attendance_value) over (
            partition by studentid, yearid order by week_start_monday
        ),
        sum(weekly_membership_value) over (
            partition by studentid, yearid order by week_start_monday
        )
    ) as ada_running
from agg_weeks
