select
    student_number,
    academic_year,
    commlog_reason,
    absence_threshold,
    days_absent_unexcused,
    commlog_notes,
    commlog_topic,
    commlog_date,
    commlog_status,
    commlog_type,
    commlog_staff_name,
    schoolid as school_id,
    intervention_status,
    intervention_status_required_int,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "academic_year", "commlog_reason"]
        )
    }} as interventions_key,
from {{ ref("int_students__attendance_interventions") }}
