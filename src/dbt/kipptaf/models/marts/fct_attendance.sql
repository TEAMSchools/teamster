with
    daily_attendance as (
        select *, from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
    ),

    running_calculations as (
        select
            student_number,
            schoolid as school_id,
            calendardate as date_day,
            academic_year,
            membershipvalue as membership_value,
            attendancevalue as is_present,
            is_absent,
            is_present_weighted,
            is_tardy,
            is_ontime,
            is_oss,
            is_iss,
            is_suspended,
            semester,
            term,
            att_code as attendance_code,

            avg(attendancevalue) over (
                partition by studentid, academic_year order by calendardate
            ) as ada_running,
            avg(is_ontime) over (
                partition by student_number, academic_year order by calendardate
            ) as pct_ontime_running,
            max(is_suspended) over (
                partition by student_number, academic_year order by calendardate
            ) as is_suspended_running,
        from daily_attendance
    ),

    final as (
        select
            *,
            if(running_calculations.ada_running <= .90, 1, 0) as is_chronic_absentee,
            if(
                running_calculations.pct_ontime_running < .795, 1, 0
            ) as is_chronic_tardy,
        from running_calculations
    )

select *,
from final
