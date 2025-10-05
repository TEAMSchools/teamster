select
    cw.student_number,
    cw.state_studentnumber,
    cw.student_name,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
    cw.region,
    cw.school_level,
    cw.schoolid,
    cw.school,
    cw.grade_level,
    cw.gender,
    cw.ethnicity,
    cw.iep_status,
    cw.is_504,
    cw.lep_status,
    cw.gifted_and_talented,
    cw.entrydate,
    cw.exitdate,
    cw.enroll_status,

    dl.incentive_type,

    if(dl.behavior is not null, 1, 0) as is_receiving_incentive,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
left join
    {{ ref("int_deanslist__behavior_incentive_by_term") }} as dl
    on cw.student_number = dl.student_school_id
    and cw.academic_year = dl.academic_year
    and cw.week_start_monday between dl.start_date and dl.end_date
    and dl.incentive_type = 'Weeks (Progress to Quarterly Incentive)'
    and cw.is_enrolled_week
