select
    student_number,
    commlog_reason,
    absence_threshold,
    commlog_notes,
    commlog_topic,
    commlog_date,
    commlog_status,
    commlog_type,
    commlog_staff_name,
    schoolid as school_id,
    if(reason is not null, 'Complete', 'Missing') as intervention_status,
    if(reason is not null, 1, 0) as intervention_status_required_int,

from {{ ref("int_students__attendance_interventions") }}
