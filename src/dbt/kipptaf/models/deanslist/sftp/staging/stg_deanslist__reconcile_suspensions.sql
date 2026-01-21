select
    schoolname as school_name,
    studentfirst as student_first_name,
    studentlast as student_last_name,
    consequence,
    attendancebehavior as attendance_behavior,
    submittedfn as submitted_first_name,
    submittedln as submitted_last_name,

    cast(dlincidentid as int) as dl_incident_id,
    cast(dlpenaltyid as int) as dl_penalty_id,
    cast(studentid as int) as student_id,

    cast(attendancedate as date) as attendance_date,
    cast(conend as date) as consequence_end_date,
    cast(constart as date) as consequence_start_date,
    cast(submittedat as datetime) as submitted_at,
from {{ source("deanslist", "src_deanslist__reconcile_suspensions") }}
