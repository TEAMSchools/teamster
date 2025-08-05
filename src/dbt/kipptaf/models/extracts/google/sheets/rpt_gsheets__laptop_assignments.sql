select
    region,
    school_abbreviation as school,
    student_number,
    lastfirst as student_name,
    grade_level,
    advisory_name,
    advisor_lastfirst,
    student_web_id as username,
    student_email_google as email,

    if(enroll_status = 2, exitdate, null) as exitdate,
    case
        when enroll_status = 0
        then 'Currently Enrolled'
        when enroll_status = 2
        then 'Transferred Out'
        when enroll_status = -1
        then 'Pre-Registered'
    end as enroll_status,
from {{ ref("base_powerschool__student_enrollments") }}
where
    is_enrolled_y1
    and rn_year = 1
    and academic_year = {{ var("current_academic_year") }}
