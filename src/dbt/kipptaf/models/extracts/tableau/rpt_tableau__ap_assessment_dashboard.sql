with
    -- A student can have two course_enrollments rows tagged with the same
    -- ap_course_subject (e.g. a main AP course plus a companion recitation
    -- section) -- both are legitimate, distinct course offerings, not a data
    -- error, so they're intentionally left undeduped here and surface as
    -- separate rows below. Distinct from the PowerSchool double-write corpus
    -- (#3900/#3915), which is literal duplicate records for the same
    -- enrollment.
    course_enrollments as (
        select
            _dbt_source_project,
            cc_studentid,
            cc_academic_year,
            ap_course_subject,
            cc_dateenrolled,
            cc_dateleft,
            sections_external_expression,
            teacher_lastfirst,
            courses_course_name,

        from {{ ref("base_powerschool__course_enrollments") }}
        where
            rn_course_number_year = 1
            and ap_course_subject is not null
            and not is_dropped_section
    ),

    ap_assessments as (
        select
            academic_year,
            powerschool_student_number,
            test_name,
            test_subject,
            exam_score,
            irregularity_code_1,
            irregularity_code_2,
            `data_source`,
            ps_ap_course_subject_code,
            ap_course_name,

        from {{ ref("int_assessments__ap_assessments") }}
        where test_subject != 'Calculus BC: AB Subscore'
    ),

    subjects as (
        select
            e.studentid,
            e.student_number,
            e.academic_year,
            e._dbt_source_project,
            c.ap_course_subject as subject_code,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            course_enrollments as c
            on e.studentid = c.cc_studentid
            and e.academic_year = c.cc_academic_year
            and e._dbt_source_project = c._dbt_source_project

        union distinct

        select
            e.studentid,
            e.student_number,
            e.academic_year,
            e._dbt_source_project,
            ap.ps_ap_course_subject_code as subject_code,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            ap_assessments as ap
            on e.academic_year = ap.academic_year
            and e.student_number = ap.powerschool_student_number
            and ap.ps_ap_course_subject_code is not null
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
    e.graduation_year,

    sub.subject_code,

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
    a.ps_ap_course_subject_code,

    coalesce(x.ap_course_name, a.ap_course_name, 'Not an AP course') as ap_course_name,

    coalesce(s.courses_course_name, 'Not an AP course') as course_name,

    case
        when s.courses_course_name is null and a.test_name is null
        then 'Not applicable'
        when s.courses_course_name is not null and a.test_name is null
        then 'Took course, but not AP exam.'
        when s.courses_course_name is null and a.test_name is not null
        then 'Took AP exam, not enrolled in course.'
        else a.ap_course_name
    end as test_subject_area,

    if(e.iep_status = 'No IEP', 0, 1) as sped,

    if(s.courses_course_name is null, 'Not applicable', 'AP') as expected_scope,

    if(
        s.courses_course_name is null, 'Not applicable', 'Official'
    ) as expected_test_type,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    subjects as sub
    on e.studentid = sub.studentid
    and e.academic_year = sub.academic_year
    and e._dbt_source_project = sub._dbt_source_project
left join
    course_enrollments as s
    on sub.studentid = s.cc_studentid
    and sub.academic_year = s.cc_academic_year
    and sub.subject_code = s.ap_course_subject
    and sub._dbt_source_project = s._dbt_source_project
left join
    ap_assessments as a
    on sub.student_number = a.powerschool_student_number
    and sub.academic_year = a.academic_year
    and sub.subject_code = a.ps_ap_course_subject_code
left join
    {{ ref("stg_google_sheets__collegeboard__ap_course_crosswalk") }} as x
    on sub.subject_code = x.ps_ap_course_subject_code
    and x.data_source = 'CB File'
where
    e.rn_year = 1
    and e.school_level = 'HS'
    and date(e.academic_year + 1, 05, 01) between e.entrydate and e.exitdate
