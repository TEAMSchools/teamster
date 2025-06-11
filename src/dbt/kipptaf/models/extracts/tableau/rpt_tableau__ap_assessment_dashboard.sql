with
    ap_course_crosswalk as (
        -- trunk-ignore(sqlfluff/RF02)
        select x.data_source, x.ap_course_name, p as ps_ap_course_subject_code,
        from {{ ref("stg_collegeboard__ap_course_crosswalk") }} as x
        cross join split(x.ps_ap_course_subject_code, ',') as p
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

    a.test_name,
    a.test_subject,
    a.exam_score,
    a.irregularity_code_1,
    a.irregularity_code_2,
    a.data_source,

    coalesce(
        a.ps_ap_course_subject_code, x.ps_ap_course_subject_code
    ) as ps_ap_course_subject_code,

    coalesce(a.ap_course_name, x.ap_course_name) as ap_course_name,

    coalesce(s.courses_course_name, 'Not an AP course') as course_name,

    case
        when s.courses_course_name is null
        then 'Not applicable'
        when s.courses_course_name is not null and a.test_name is null
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
    and s.ap_course_subject is not null
    and not s.is_dropped_section
left join
    ap_course_crosswalk as x
    on s.ap_course_subject = x.ps_ap_course_subject_code
    and x.data_source = 'CB File'
left join
    {{ ref("int_assessments__ap_assessments") }} as a
    on e.academic_year = a.academic_year
    and e.student_number = a.powerschool_student_number
    and s.ap_course_subject = a.ps_ap_course_subject_code
    and a.test_subject != 'Calculus BC: AB Subscore'
where
    e.school_level = 'HS'
    and date(e.academic_year + 1, 05, 15) between e.entrydate and e.exitdate
