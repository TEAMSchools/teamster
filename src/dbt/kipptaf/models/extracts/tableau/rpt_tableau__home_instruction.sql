select
    co.student_number,
    co.student_name,
    co.academic_year,
    co.grade_level,
    co.region,
    co.school,
    co.iep_status,
    co.gender,
    co.ethnicity,
    co.lep_status,
    co.is_504,
    co.enroll_status,
    co.team,
    co.advisor_lastfirst as advisor,

    dli.incident_id,
    dli.status,
    dli.reported_details,
    dli.admin_summary,
    dli.context,
    dli.infraction,
    dli.final_approval,
    dli.instructor_source,
    dli.instructor_name,
    dli.hours_per_week,
    dli.hourly_rate,
    dli.board_approval_date,
    dli.hi_start_date,
    dli.hi_end_date,
    dli.approver_name,
    dli.create_lastfirst as referring_staff_name,
    dli.update_lastfirst as reviewing_staff_name,
from {{ ref("int_extracts__student_enrollments") }} as co
inner join
    {{ ref("int_deanslist__incidents__penalties") }} as dli
    on co.academic_year = dli.create_ts_academic_year
    and co.student_number = dli.student_school_id
    and co.deanslist_school_id = dli.school_id
    /* TODO: Add home_instruction_reason to JOIN */
    and (dli.category = 'TX - HI Request (admin only)' or dli.hi_start_date is not null)
