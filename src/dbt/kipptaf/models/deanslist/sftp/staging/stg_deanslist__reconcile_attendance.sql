select
    schoolname as school_name,
    studentfirst as student_first_name,
    studentlast as student_last_name,
    attendancebehavior as attendance_behavior,
    submittedfn as submitted_first_name,
    submittedln as submitted_last_name,

    cast(studentid as int) as student_id,

    cast(attendancedate as date) as attendance_date,
    cast(submittedat as datetime) as submitted_at,
from {{ source("deanslist", "src_deanslist__reconcile_attendance") }}
