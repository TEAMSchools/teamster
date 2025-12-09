with
    daily_attendance as (
        select *, from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
    ),

    final as (
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
        from daily_attendance
    )

select *,
from final


