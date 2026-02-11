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
    is_truant,
    semester,
    term,
    att_code as attendance_code,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "calendardate", "schoolid"]
        )
    }} as attendance_key,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
