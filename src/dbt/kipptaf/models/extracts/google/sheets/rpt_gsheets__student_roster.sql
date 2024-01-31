select
    student_number,
    lastfirst as student_name,
    first_name,
    last_name,
    dob,
    student_email_google,
    grade_level,
    region,
    school_abbreviation as school,
    advisor_lastfirst,
    advisory_name,
    is_self_contained,
    is_out_of_district,
    spedlep,
    lep_status,
    is_504,
    lunch_status,
    ethnicity,
    gender,
    is_retained_year,
    is_retained_ever,

    case
        when enroll_status = 0
        then 'Currently enrolled'
        when enroll_status = -1
        then 'Pre-enrolled'
        when enroll_status = 2
        then 'Transferred out'
    end as enroll_status,
from {{ ref("base_powerschool__student_enrollments") }}
where
    academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
    and enroll_status != 3
