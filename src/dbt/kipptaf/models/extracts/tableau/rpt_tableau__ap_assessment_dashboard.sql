with
    ap_assessments_official as (
        select
            a.academic_year,
            a.school_specific_id as powerschool_student_number,
            a.`date` as test_date,
            a.score as scale_score,
            a.rn_highest,
            a.test_subject,

            null as irregularity_code_1,
            null as irregularity_code_2,

            c.ps_ap_course_subject_code,
            c.ap_course_name,

            concat(
                format_date('%b', a.`date`), ' ', format_date('%g', a.`date`)
            ) as administration_round,

        from {{ ref("int_kippadb__standardized_test_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.test_subject = c.adb_test_subject
        where
            a.score_type = 'ap' and a.academic_year < 2018 and c.ap_course_name is null

        union all

        select
            a.admin_year as academic_year,
            a.powerschool_student_number,
            null as test_date,
            a.exam_grade as scale_score,
            null as rn_highest,
            a.exam_code_description as test_subject,
            a.irregularity_code_1,
            a.irregularity_code_2,

            c.ps_ap_course_subject_code,
            c.ap_course_name,

            null as administration_round,

        from {{ ref("int_collegeboard__ap_unpivot") }} as a
        left join
            {{ ref("stg_collegeboard__ap_course_crosswalk") }} as c
            on a.exam_code = c.ps_ap_course_subject_code
    )

select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.student_name,
    e.grade_level,
    e.enroll_status,
    e.entrydate,
    e.exitdate,
    e.cohort,
    e.advisory,
    e.is_enrolled_recent,
    e.is_enrolled_y1,
    e.is_504 as c_504_status,
    e.lep_status,
    e.gifted_and_talented,
    e.salesforce_id as contact_id,
    e.ktc_cohort,

    s.cc_dateenrolled as ap_date_enrolled,
    s.cc_dateleft as ap_date_left,
    s.sections_external_expression as ap_course_section,
    s.teacher_lastfirst as ap_teacher_name,
    s.ap_course_subject,

    a.administration_round,
    a.test_date,
    a.scale_score,
    a.rn_highest,

    a.ap_course_name,

    coalesce(s.courses_course_name, 'Not an AP course') as course_name,

    case
        when s.courses_course_name is null
        then 'Not applicable'
        when s.courses_course_name is not null and a.ap_course_name is null
        then 'Took course, but not AP exam.'
        else a.ap_course_name
    end as test_subject_area,

    if(e.iep_status = 'No IEP', 0, 1) as sped,

    if(s.courses_course_name is null, 'Not applicable', 'AP') as expected_scope,

    if(
        s.courses_course_name is null, 'Not applicable', 'Official'
    ) as expected_test_type,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("base_powerschool__course_enrollments") }} as s
    on e.studentid = s.cc_studentid
    and e.academic_year = s.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
    and s.rn_course_number_year = 1
    and s.courses_course_name like 'AP%'
    and not s.is_dropped_section
left join
    ap_assessments_official as a
    on e.student_number = a.powerschool_student_number
    and s.ap_course_subject = a.ps_ap_course_subject_code
where
    e.school_level = 'HS'
    and date(e.academic_year + 1, 05, 15) between e.entrydate and e.exitdate
