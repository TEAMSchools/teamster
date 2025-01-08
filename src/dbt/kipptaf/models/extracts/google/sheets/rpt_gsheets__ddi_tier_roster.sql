select
    co.region,
    co.student_number,
    co.lastfirst as student_name,
    co.school_abbreviation as school,
    co.grade_level,
    co.advisory_name as team,
    co.spedlep as iep_status,

    f.iready_subject as subject,
    f.nj_student_tier,
    f.state_test_proficiency as njsla_previous_year,
    f.iready_proficiency_eoy as iready_eoy_previous_year,
from {{ ref("int_extracts__student_filters") }} as f
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on f.student_number = co.student_number
    and f.academic_year = co.academic_year
    and co.rn_year = 1
where
    f.nj_student_tier is not null
    and f.academic_year = {{ var("current_academic_year") }}
