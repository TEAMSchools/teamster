select
    academic_year,
    school_specific_id as powerschool_student_number,
    test_subject,
    score as exam_score,
    test_name,
    ps_ap_course_subject_code,
    ap_course_name,

    'ADB' as `data_source`,
    null as irregularity_code_1,
    null as irregularity_code_2,
from {{ ref("int_kippadb__standardized_test_unpivot") }}
where
    score_type = 'ap'
    /* 2018+ comes from CB */
    and academic_year < 2018

union all

select
    academic_year,
    powerschool_student_number,
    exam_code_description as test_subject,
    exam_grade as exam_score,
    test_name,
    ps_ap_course_subject_code,
    ap_course_name,

    'CB File' as `data_source`,

    irregularity_code_1,
    irregularity_code_2,
from {{ ref("int_collegeboard__ap_unpivot") }}
where academic_year >= 2018  /* 1st year with CB file */
