with
    roster as (
        select
            e.academic_year,
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
            e.advisory,
            e.contact_id,
            e.ktc_cohort,
            e.contact_owner_name,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,

            t.test_type as expected_test_type,
            t.scope as expected_scope,
            t.subject_area as expected_subject_area,

            if(e.iep_status = 'No IEP', 0, 1) as sped,

        from {{ ref("int_tableau__student_enrollments") }} as e
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
            and t.assessment_type = 'College Entrance'
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
    ),

    course_subjects_roster as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,
            e.contact_id,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
            s.courses_credittype,

            f.is_exempt_state_testing,

        from {{ ref("int_tableau__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.student_number = s.students_student_number
            and e.academic_year = s.cc_academic_year
            and s.courses_credittype in ('ENG', 'MATH')
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
        left join
            {{ ref("int_reporting__student_filters") }} as f
            on s.cc_academic_year = f.academic_year
            and s.students_student_number = f.student_number
            and s.courses_credittype = f.powerschool_credittype
        where e.school_level = 'HS'
    ),

    college_assessments_official as (
        select
            contact,
            test_type as scope,
            date as test_date,
            score as scale_score,
            rn_highest,

            'Official' as test_type,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            case
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                else test_subject
            end as subject_area,
            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ENG'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            {{
                date_to_fiscal_year(
                    date_field="date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
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

        union all

        select
            safe_cast(local_student_id as string) as contact,

            'PSAT10' as scope,

            test_date,
            score as scale_score,
            rn_highest,

            'Official' as test_type,

            concat(
                format_date('%b', test_date), ' ', format_date('%g', test_date)
            ) as administration_round,

            case
                score_type
                when 'psat10_total_score'
                then 'Composite'
                when 'psat10_reading_test_score'
                then 'Reading'
                when 'psat10_math_test_score'
                then 'Math Test'
                when 'psat10_math_section_score'
                then 'Math'
                when 'psat10_eb_read_write_section_score'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when
                    score_type in (
                        'psat10_eb_read_write_section_score',
                        'psat10_reading_test_score'
                    )
                then 'ENG'
                when
                    score_type
                    in ('psat10_math_test_score', 'psat10_math_section_score')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            academic_year as test_academic_year,
        from {{ ref("int_illuminate__psat_unpivot") }}
        where
            score_type in (
                'psat10_eb_read_write_section_score',
                'psat10_math_section_score',
                'psat10_math_test_score',
                'psat10_reading_test_score',
                'psat10_total_score'
            )
    )

select
    e.academic_year,
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
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
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

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,
from roster as e
left join
    college_assessments_official as o
    on e.contact_id = o.contact
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
left join
    course_subjects_roster as c
    on o.contact = c.contact_id
    and o.test_academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.expected_test_type = 'Official' and e.expected_scope in ('ACT', 'SAT')

union all

select
    e.academic_year,
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
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
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

    coalesce(c.is_exempt_state_testing, false) as is_exempt_state_testing,
from roster as e
left join
    college_assessments_official as o
    on safe_cast(e.student_number as string) = o.contact
    and e.expected_test_type = o.test_type
    and e.expected_scope = o.scope
    and e.expected_subject_area = o.subject_area
left join
    course_subjects_roster as c
    on o.contact = c.contact_id
    and o.test_academic_year = c.academic_year
    and o.course_discipline = c.courses_credittype
where e.expected_test_type = 'Official' and e.expected_scope = 'PSAT10'

union all

select
    e.academic_year,
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
    e.advisory,
    e.contact_id,
    e.ktc_cohort,
    e.contact_owner_name,
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
