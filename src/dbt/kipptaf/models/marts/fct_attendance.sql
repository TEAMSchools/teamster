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
            max(calendardate) over (
                partition by student_number, academic_year
            ) as student_max_date,
        from daily_attendance
    ),

    student_max_date as (
        select *, if(date_day = student_max_date, true, false) as is_student_max_date,
        from running_calculations
    ),

    student_max_values as (
        select
            student_number,
            school_id,
            date_day,
            academic_year,
            membership_value,
            is_present,
            is_absent,
            is_present_weighted,
            is_tardy,
            is_ontime,
            is_oss,
            is_iss,
            is_suspended,
            semester,
            term,
            attendance_code,
            ada_running,
            pct_ontime_running,
            if(is_student_max_date, ada_running, null) as ada_running_student_max,
            if(
                is_student_max_date, ada_running, null
            ) as pct_ontime_running_student_max,
        from student_max_date
    ),

    final as (
        select
            *,
            if(
                student_max_values.ada_running_student_max <= .90, 1, 0
            ) as is_chronic_absentee,
            if(
                student_max_values.pct_ontime_running_student_max <= .90, 1, 0
            ) as is_chronic_tardy,
        from student_max_values
    )

select *,
from final
