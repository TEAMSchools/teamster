select
    region,
    student_number,
    lastfirst as student_name,
    school_abbreviation as school,
    grade_level,
    advisory_name as team,
    spedlep as iep_status,
    iready_subject as `subject`,
    nj_student_tier,
    state_test_proficiency as njsla_previous_year,
    iready_proficiency_eoy as iready_eoy_previous_year,
from {{ ref("int_extracts__student_enrollments_subjects") }}
where
    nj_student_tier is not null
    and academic_year = {{ var("current_academic_year") }}
    and rn_year = 1
