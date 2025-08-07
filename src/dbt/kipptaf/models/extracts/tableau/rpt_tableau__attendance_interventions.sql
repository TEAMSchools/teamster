select
    co.student_number,
    co.student_name,
    co.grade_level,
    co.team,
    co.region,
    co.school,

    ai.commlog_reason,
    ai.absence_threshold,
    ai.days_absent_unexcused,
    ai.commlog_staff_name,
    ai.commlog_notes,
    ai.commlog_topic,
    ai.commlog_date,
    ai.commlog_status,
    ai.commlog_type,
    ai.intervention_status,
    ai.intervention_status_required_int,
from {{ ref("int_topline__attendance_interventions") }} as ai
inner join
    {{ ref("int_extracts__student_enrollments") }} as co
    on ai.student_number = co.student_number
    and ai.academic_year = co.academic_year
    and co.enroll_status = 0
where co.academic_year = {{ var("current_academic_year") }}
