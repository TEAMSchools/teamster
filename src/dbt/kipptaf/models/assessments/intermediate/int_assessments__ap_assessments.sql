with
    adb_scores as (
        select
            a.academic_year,
            a.school_specific_id as powerschool_student_number,
            a.`date` as test_date,
            a.score as scale_score,
            a.rn_highest,
            a.test_subject,

            c.ps_ap_course_subject_code,
            c.ps_ap_course_subject_name,
            c.ap_course_name,

            concat(
                format_date('%b', a.`date`), ' ', format_date('%g', a.`date`)
            ) as administration_round,

            row_number() over (
                partition by
                    a.academic_year, a.school_specific_id, a.test_subject, a.score
                order by a.rn_highest desc
            ) as rn_distinct,

        from {{ ref("int_kippadb__standardized_test_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.test_subject = c.adb_test_subject
        where
            a.score_type = 'ap'
            and a.academic_year < 2018
            and a.test_subject != 'Calculus BC: AB Subscore'
    )

select
    academic_year,
    powerschool_student_number,
    test_subject,
    scale_score,

    null as irregularity_code_1,
    null as irregularity_code_2,

    ps_ap_course_subject_code,
    ps_ap_course_subject_name,
    ap_course_name,

    administration_round,
    test_date,
    rn_highest,

from adb_scores
where rn_distinct = 1

union all

select
    a.admin_year as academic_year,
    a.powerschool_student_number,
    a.exam_code_description as test_subject,
    a.exam_grade as scale_score,

    a.irregularity_code_1,
    a.irregularity_code_2,

    c.ps_ap_course_subject_code,
    c.ps_ap_course_subject_name,
    c.ap_course_name,

    null as administration_round,
    null as test_date,
    null as rn_highest,

from {{ ref("int_collegeboard__ap_unpivot") }} as a
left join
    {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
    on a.exam_code_description = c.ps_ap_course_subject_name
where a.exam_code_description != 'Calculus BC: AB Subscore' and a.rn_distinct = 1
