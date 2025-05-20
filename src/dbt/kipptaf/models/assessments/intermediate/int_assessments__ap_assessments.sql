with
    adb_scores as (
        select
            a.academic_year,
            a.school_specific_id as powerschool_student_number,
            a.score as exam_score,
            a.test_subject,

            c.test_name,
            c.ps_ap_course_subject_code,
            c.ap_course_name,
            c.data_source,

            row_number() over (
                partition by
                    a.academic_year, a.school_specific_id, a.test_subject, a.score
                order by a.date desc
            ) as rn_distinct,

        from {{ ref("int_kippadb__standardized_test_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.test_subject = c.test_name
            and c.data_source = 'ADB'
        where a.score_type = 'ap' and a.academic_year < 2018
    ),

    cb_scores as (
        select
            a.academic_year,
            a.powerschool_student_number,
            a.exam_code_description as test_subject,
            a.exam_grade as exam_score,

            a.irregularity_code_1,
            a.irregularity_code_2,

            c.test_name,
            c.ps_ap_course_subject_code,
            c.ap_course_name,
            c.data_source,

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
            on a.exam_code_description = c.test_name
            and c.data_source = 'CB File'
        where a.academic_year >= 2018
    )

select
    academic_year,
    powerschool_student_number,
    test_subject,
    exam_score,
    test_name,
    ps_ap_course_subject_code,
    ap_course_name,
    data_source,

    null as irregularity_code_1,
    null as irregularity_code_2,

from adb_scores
where rn_distinct = 1

union all

select
    academic_year,
    powerschool_student_number,
    test_subject,
    exam_score,
    test_name,
    ps_ap_course_subject_code,
    ap_course_name,
    data_source,

    irregularity_code_1,
    irregularity_code_2,

from cb_scores
where rn_distinct = 1
