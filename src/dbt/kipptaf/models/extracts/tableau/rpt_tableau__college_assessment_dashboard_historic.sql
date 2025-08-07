with
    base_courses as (
        /*
            this CTE and the following one were added to help figure out which base
            course to pick for a student, since not all of them have CCR, and not all
            have HR, so i wrote this to try to catch everyone possible
        */
        select
            _dbt_source_relation,
            cc_academic_year,
            students_student_number as student_number,
            courses_course_name,

            if(courses_course_name = 'HR', 2, 1) as course_rank,

            min(if(courses_course_name = 'HR', 2, 1)) over (
                partition by cc_academic_year, students_student_number
            ) as expected_course_rank,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_name in (
                'HR',
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II'
            )
            and rn_course_number_year = 1
            and not is_dropped_section
    ),

    expected_course as (
        select distinct
            _dbt_source_relation,
            cc_academic_year,
            student_number,
            courses_course_name as courses_course_name_expected,
        from base_courses
        where course_rank = expected_course_rank
    ),

    roster as (
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
            e.cohort,
            e.entrydate,
            e.exitdate,
            e.is_504 as c_504_status,
            e.lep_status,
            e.gifted_and_talented,
            e.advisory,
            e.salesforce_id as contact_id,
            e.ktc_cohort,
            e.contact_owner_name,
            e.college_match_gpa,
            e.college_match_gpa_bands,
            e.ms_attended,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

            if(e.iep_status = 'No IEP', 0, 1) as sped,

            coalesce(f.is_exempt_state_testing, false) as dlm,
        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II',
                'HR'
            )
        left join
            expected_course as ec
            on s.cc_academic_year = ec.cc_academic_year
            and s.students_student_number = ec.student_number
            and s.courses_course_name = ec.courses_course_name_expected
            and {{ union_dataset_join_clause(left_alias="s", right_alias="ec") }}
        left join
            {{ ref("int_extracts__student_enrollments_subjects") }} as f
            on s.cc_academic_year = f.academic_year
            and s.students_student_number = f.student_number
            and s.courses_credittype = f.powerschool_credittype
            and f.rn_year = 1
        where
            e.rn_year = 1
            and e.school_level = 'HS'
            and ec.courses_course_name_expected is not null
    ),

    college_assessments_official as (
        select
            student_number,
            scope,
            test_date,
            administration_round,
            subject_area,
            scale_score,
            rn_highest,

            'Official' as test_type,

            if(
                subject_area in ('Composite', 'Combined'), 'NA', course_discipline
            ) as course_discipline,

            {{
                date_to_fiscal_year(
                    date_field="test_date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from {{ ref("int_assessments__college_assessment") }}
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'act_english',
                'act_science',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )
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
    e.cohort,
    e.entrydate,
    e.exitdate,
    e.sped,
    e.c_504_status,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.dlm,
    e.ms_attended,

    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
    o.test_academic_year,
    o.subject_area,
    o.test_date,

    'NA' as response_type,
    'NA' as response_type_description,

    null as points,
    null as percent_correct,
    null as total_subjects_tested,
    null as raw_score,

    o.scale_score,
    o.rn_highest,
from roster as e
left join
    college_assessments_official as o
    on e.student_number = o.student_number
    and e.academic_year = o.test_academic_year
where o.test_type = 'Official'

union all

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
    e.cohort,
    e.entrydate,
    e.exitdate,
    e.sped,
    e.c_504_status,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.dlm,
    e.ms_attended,

    p.test_type,
    p.scope,
    p.scope_round,
    p.assessment_id,
    p.assessment_title,
    p.administration_round,
    p.academic_year as test_academic_year,
    p.subject_area,
    p.test_date,
    p.response_type,
    p.response_type_description,
    p.points,
    p.percent_correct,
    p.total_subjects_tested,
    p.raw_score,
    p.scale_score,

    row_number() over (
        partition by e.student_number, p.scope, p.subject_area
        order by p.scale_score desc
    ) as rn_highest,
from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
where p.test_type = 'Practice'
