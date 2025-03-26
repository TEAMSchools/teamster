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
            and rn_credittype_year = 1
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
            e._dbt_source_relation,
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
            e.is_504,
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

            t.test_type as expected_test_type,
            t.scope as expected_scope,
            t.subject_area as expected_subject_area,
            t.test_code as expected_administration_round,
            t.admin_season as expected_admin_season,
            t.month_round as expected_month_round,

            if(e.iep_status = 'No IEP', 0, 1) as sped,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.student_number = s.students_student_number
            and e.academic_year = s.cc_academic_year
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
            and s.courses_course_name in (
                'College and Career IV',
                'College and Career I',
                'College and Career III',
                'College and Career II',
                'HR'
            )
        inner join
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
        left join
            {{ ref("stg_assessments__assessment_expectations") }} as t
            on e.academic_year = t.academic_year
            and e.grade_level = t.grade
            and e.region = t.region
            and t.assessment_type = 'College Entrance'
        where e.school_level = 'HS' and ec.courses_course_name_expected is not null
    ),

    course_subjects_roster as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,
            e.salesforce_id as contact_id,
            e.is_exempt_state_testing,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
            s.courses_credittype,

            if(
                s.courses_course_number = 'MAT02056D3', true, false
            ) as is_math_double_blocked,

        from {{ ref("int_extracts__student_enrollments_subjects") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.student_number = s.students_student_number
            and e.academic_year = s.cc_academic_year
            and e.powerschool_credittype = s.courses_credittype
            and s.rn_course_number_year = 1
            and s.courses_credittype in ('ENG', 'MATH')
            and not s.is_dropped_section
        where e.school_level = 'HS'
    )

select
    e._dbt_source_relation,
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
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.ms_attended,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    -- e.expected_test_code,
    -- e.expected_admin_season,
    -- e.expected_month_round,
    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
    c.is_math_double_blocked,

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,

from roster as e
left join
    {{ ref("int_assessments__college_assessment") }} as o
    on e.contact_id = o.salesforce_id
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where
    e.expected_test_type = 'Official'
    and e.expected_scope in ('ACT', 'SAT')
    and e.academic_year >= 2023

union all

select
    e._dbt_source_relation,
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
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.ms_attended,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,

    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
    c.is_math_double_blocked,

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,

from roster as e
left join
    {{ ref("int_assessments__college_assessment") }} as o
    on e.student_number = o.student_number
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where
    e.expected_test_type = 'Official'
    and e.expected_scope in ('PSAT NMSQT', 'PSAT 8/9', 'PSAT10')
    and e.academic_year >= 2023

union all

select
    e._dbt_source_relation,
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
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.ms_attended,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,

    o.test_type as expected_test_type,
    o.scope as expected_scope,
    o.subject_area as expected_subject_area,

    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
    c.is_math_double_blocked,

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,

from roster as e
left join
    {{ ref("int_assessments__college_assessment") }} as o
    on e.academic_year = o.academic_year
    and e.contact_id = o.salesforce_id
    and o.scope in ('ACT', 'SAT')
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.academic_year < 2023

union all

select
    e._dbt_source_relation,
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
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.ms_attended,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,

    o.test_type as expected_test_type,
    o.scope as expected_scope,
    o.subject_area as expected_subject_area,

    o.test_type,
    o.scope,

    'NA' as scope_round,
    null as assessment_id,
    'NA' as assessment_title,

    o.administration_round,
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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
    c.is_math_double_blocked,

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,

from roster as e
left join
    {{ ref("int_assessments__college_assessment") }} as o
    on e.academic_year = o.academic_year
    and e.student_number = o.student_number
    and o.scope in ('PSAT NMSQT', 'PSAT 8/9', 'PSAT10')
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.academic_year < 2023

union all

select
    e._dbt_source_relation,
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
    e.is_504,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.ms_attended,
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,

    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,

    p.test_type,
    p.scope,
    p.scope_round,
    p.assessment_id,
    p.assessment_title,
    p.administration_round,
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

    c.courses_course_name as subject_course,
    c.teacher_lastfirst as subject_teacher,
    c.sections_external_expression as subject_external_expression,
    c.is_math_double_blocked,

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,

from roster as e
left join
    {{ ref("int_assessments__college_assessment_practice") }} as p
    on e.student_number = p.powerschool_student_number
    and e.academic_year = p.academic_year
    and e.expected_test_type = p.test_type
    and e.expected_scope = p.scope
    and e.expected_subject_area = p.subject_area
left join
    course_subjects_roster as c
    on p.powerschool_student_number = c.student_number
    and p.academic_year = c.academic_year
    and p.course_discipline = c.courses_credittype
where e.expected_test_type = 'Practice'
