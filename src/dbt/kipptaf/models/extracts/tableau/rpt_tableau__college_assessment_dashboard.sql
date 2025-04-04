with
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
            e.is_504,
            e.lep_status,
            e.gifted_and_talented,
            e.advisory,
            e.salesforce_id as contact_id,
            e.ktc_cohort,
            e.contact_owner_name,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

            t.test_type as expected_test_type,
            t.scope as expected_scope,
            t.subject_area as expected_subject_area,
            t.assessment_subject_area as expected_score_type,
            t.test_code as expected_test_code,
            t.admin_season as expected_admin_season,
            t.month_round as expected_month_round,
            t.actual_month_round as expected_actual_month_round,
            t.strategy,

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
                'College and Career II'
            )
        left join
            {{ ref("stg_assessments__assessment_expectations") }} as t
            on e.academic_year = t.academic_year
            and e.grade_level = t.grade
            and e.region = t.region
            and t.assessment_type = 'College Entrance'
            and t.strategy
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
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
    ),

    custom_scores as (
        select
            o.* except (test_month),
            t.test_code,
            t.admin_season,
            t.month_round,
            t.strategy,
            t.actual_month_round,

        from {{ ref("int_assessments__college_assessment") }} as o
        inner join
            {{ ref("stg_assessments__assessment_expectations") }} as t
            on o.academic_year = t.academic_year
            and o.test_type = t.test_type
            and o.score_type = t.assessment_subject_area
            and o.test_month = t.month_round
            and t.assessment_type = 'College Entrance'
            and t.strategy

        union all

        select
            o.* except (test_month),
            t.test_code,
            t.admin_season,
            t.month_round,
            t.strategy,
            t.actual_month_round,

        from {{ ref("int_assessments__college_assessment") }} as o
        inner join
            {{ ref("stg_assessments__assessment_expectations") }} as t
            on o.academic_year = t.academic_year
            and o.test_type = t.test_type
            and o.score_type = t.assessment_subject_area
            and o.test_month = t.actual_month_round
            and t.assessment_type = 'College Entrance'
            and t.grade = 11
            and t.scope = 'SAT'
            and not t.strategy
    ),

    scores as (
        select
            *,
            row_number() over (
                partition by
                    academic_year,
                    student_number,
                    salesforce_id,
                    score_type,
                    test_code,
                    admin_season,
                    month_round
            ) as rn_distinct,
        from custom_scores
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
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.expected_score_type,
    e.expected_test_code,
    e.expected_admin_season,
    e.expected_month_round,
    e.expected_actual_month_round,
    e.strategy,

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
<<<<<<< HEAD
<<<<<<< HEAD
    scores as o
    on e.contact_id = o.salesforce_id
=======
    {{ ref("int_assessments__college_assessment") }} as o
    on e.student_number = o.student_number
>>>>>>> 72d81821108d4c73cedf7611fd0e9a5caae66b1b
=======
    {{ ref("int_assessments__college_assessment") }} as o
    on e.student_number = o.student_number
>>>>>>> 72d81821108d4c73cedf7611fd0e9a5caae66b1b
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_score_type = o.score_type
    and o.rn_distinct = 1
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.expected_test_type = 'Official' and e.expected_scope in ('ACT', 'SAT')

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
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.expected_score_type,
    e.expected_test_code,
    e.expected_admin_season,
    e.expected_month_round,
    e.expected_actual_month_round,
    e.strategy,

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
    scores as o
    on e.student_number = o.student_number
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
    and o.rn_distinct = 1
left join
    course_subjects_roster as c
    on e.student_number = c.student_number
    and e.academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where
    e.expected_test_type = 'Official' and e.expected_scope in ('PSAT NMSQT', 'PSAT 8/9')

-- this code is a placeholder for now, as we are not reporting practice scores for
-- sy2425, but will do so again for sy2526
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
    e.courses_course_name,
    e.teacher_lastfirst,
    e.sections_external_expression,
    e.expected_test_type,
    e.expected_scope,
    e.expected_subject_area,
    e.expected_score_type,
    e.expected_test_code,
    e.expected_admin_season,
    e.expected_month_round,
    e.expected_actual_month_round,
    true as strategy,

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
where e.expected_test_type = 'Practice' and e.strategy
