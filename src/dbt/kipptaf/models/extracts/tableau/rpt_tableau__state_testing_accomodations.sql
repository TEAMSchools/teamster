select
    co.student_number,
    co.state_studentnumber,
    co.student_name as lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.school_name,
    co.grade_level,
    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.spedlep as iep_status,
    co.special_education_code as specialed_classification,
    co.lep_status,
    co.is_504 as c_504_status,

    ac.asmt_exclude_ela,
    ac.asmt_exclude_math,
    ac.math_state_assessment_name,
    ac.parcc_test_format,
    ac.state_assessment_name,
    ac.name_column as accommodation,
    ac.values_column as accommodation_value,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as ac
    on co.students_dcid = ac.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ac") }}
    and ac.value_type = 'Accomodation'
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.region in ('Newark', 'Camden')
