select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ed.student_number",
                "ed._dbt_source_project",
                "ed.calendardate",
            ]
        )
    }} as student_day_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "ed.student_number",
                "ed._dbt_source_project",
                "ed.academic_year",
                "ed.entrydate",
            ]
        )
    }} as student_enrollment_key,

    ed.calendardate as date_key,
    ed.is_in_session_day,

    t.term_key,

    ada.att_code as attendance_code,

    ada.attendancevalue as attendance_value,
    ada.is_present_weighted as present_weight,

    ada.is_truant,

    coalesce(ada.membershipvalue, ed.membershipvalue) as membership_value,

    cast(ada.is_absent as int64) as is_absent,
    cast(ada.is_tardy as int64) as is_tardy,
    cast(ada.is_ontime as int64) as is_ontime,
    cast(ada.is_oss as int64) as is_oss,
    cast(ada.is_iss as int64) as is_iss,
    cast(ada.is_suspended as int64) as is_suspended,

    -- Null, not 'Present', when no attendance row joined. A carried break day
    -- and a session day with an unrecorded register both land here, and both
    -- mean unknown rather than present.
    case
        when ada.is_absent is null
        then null
        when ada.is_oss = 1
        then 'Out-of-School Suspension'
        when ada.is_iss = 1
        then 'In-School Suspension'
        when ada.is_absent = 1
        then 'Absent'
        when ada.is_tardy = 1
        then 'Tardy'
        else 'Present'
    end as attendance_category,
from {{ ref("int_students__enrollment_days") }} as ed
-- Keyed on student-day, deliberately without entrydate. The enrollment spine
-- and the attendance model can date the same stint differently across the
-- Focus cutover, and int_students__attendance_daily is unique on student-day,
-- so dropping entrydate from the key costs no fan-out and loses no rows.
left join
    {{ ref("int_students__attendance_daily") }} as ada
    on ed.student_number = ada.student_number
    and ed._dbt_source_project = ada._dbt_source_project
    and ed.calendardate = ada.calendardate
left join
    {{ ref("dim_terms") }} as t
    on ed.schoolid = t.school_id
    and ed.term = t.term_name
    and ed.academic_year = t.academic_year
    and t.`type` = 'RT'
