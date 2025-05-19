with
    adb_scores as (
        select
            a.academic_year,
            a.school_specific_id as powerschool_student_number,
            a.score as exam_score,
            a.test_subject,

            c.ps_ap_course_subject_code,
            c.ps_ap_course_subject_name,
            c.ap_course_name,

            row_number() over (
                partition by
                    a.academic_year, a.school_specific_id, a.test_subject, a.score
                order by a.date desc
            ) as rn_distinct,
        from {{ ref("int_kippadb__standardized_test_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.test_subject = c.adb_test_subject
        where
            a.score_type = 'ap'
            and a.academic_year < 2017
            and a.test_subject != 'Calculus BC: AB Subscore'
    ),

    cb_scores as (
        select
            a.academic_year,
            a.powerschool_student_number,
            a.exam_code_description as test_subject,
            a.exam_grade as exam_score,

            a.irregularity_code_1,
            a.irregularity_code_2,

            c.ps_ap_course_subject_code,
            c.ps_ap_course_subject_name,
            c.ap_course_name,

            row_number() over (
                partition by
                    a.academic_year,
                    a.powerschool_student_number,
                    a.exam_code_description,
                    a.exam_grade
                order by a.rn_exam_number desc
            ) as rn_distinct,
        from {{ ref("int_collegeboard__ap_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.exam_code_description = c.ps_ap_course_subject_name
        where
            a.exam_code_description != 'Calculus BC: AB Subscore'
            and a.academic_year >= 2018
    )

select
    academic_year,
    powerschool_student_number,
    test_subject,
    exam_score,
    ps_ap_course_subject_code,
    ps_ap_course_subject_name,
    ap_course_name,

    null as irregularity_code_1,
    null as irregularity_code_2,
    'ADB' as `data_source`,
from adb_scores
where rn_distinct = 1

union all

select
    academic_year,
    powerschool_student_number,
    test_subject,
    exam_score,
    ps_ap_course_subject_code,
    ps_ap_course_subject_name,
    ap_course_name,
    irregularity_code_1,
    irregularity_code_2,

    'CB File' as `data_source`,
from cb_scores
where rn_distinct = 1
