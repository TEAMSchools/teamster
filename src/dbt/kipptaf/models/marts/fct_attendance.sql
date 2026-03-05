with
    daily_attendance as (
        select
            student_number,
            calendardate as attendance_date,
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
            is_truant,
            semester,
            term,
            att_code as attendance_code,
            {{ dbt_utils.generate_surrogate_key(["student_number", "calendardate"]) }}
            as attendance_key,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
    )

    final as (
        select
            student_number,
            attendance_date,
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
            is_truant,
            semester,
            term,
            attendance_code,
            attendance_key,
        from daily_attendance
    )

select *
from final
