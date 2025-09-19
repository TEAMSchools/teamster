with
    strategy as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            a.academic_year as expected_test_academic_year,
            a.test_type as expected_test_type,
            a.test_date as expected_test_date,
            a.test_month as expected_test_month,
            a.scope as expected_scope,
            a.subject_area as expected_subject_area,
            a.score_type as expected_score_type,

            e.grade_level as expected_grade_level,

        from {{ ref("int_assessments__college_assessment") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            a.score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    crosswalk as (
        select
            expected_test_academic_year,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            expected_grade_level,
            expected_test_date,
            expected_test_month,

            concat(
                'G', expected_grade_level, ' ', left(expected_test_month, 3)
            ) as expected_test_admin_for_over_time,

            concat(
                'G',
                expected_grade_level,
                ' ',
                expected_test_month,
                ' ',
                expected_scope,
                ' ',
                expected_test_type,
                ' ',
                expected_subject_area
            ) as expected_field_name,

            case
                expected_scope
                when 'ACT'
                then 1
                when 'SAT'
                then 2
                when 'PSAT NMSQT'
                then 3
                when 'PSAT10'
                then 4
                when 'PSAT 8/9'
                then 5
            end as expected_scope_order,

            case
                when expected_subject_area in ('Combined', 'Composite')
                then 1
                when expected_score_type = 'act_reading'
                then 2
                when expected_score_type = 'act_math'
                then 3
                when expected_score_type = 'act_english'
                then 4
                when expected_score_type = 'act_science'
                then 5
                when expected_subject_area = 'EBRW'
                then 2
                when expected_subject_area = 'Math'
                then 3
            end as expected_subject_area_order,

            if(
                extract(month from expected_test_date) >= 8,
                extract(month from expected_test_date) - 7,
                extract(month from expected_test_date) + 5
            ) as expected_month_order,

        from strategy
    ),

    additional_fields as (
        select
            *,

            concat(
                expected_scope_order,
                '_',
                expected_subject_area_order,
                '_',
                expected_month_order
            ) as expected_admin_order,

            lower(
                concat(
                    'G',
                    expected_grade_level,
                    '_',
                    expected_month_order,
                    '_',
                    expected_test_type,
                    '_',
                    expected_scope_order,
                    '_',
                    expected_subject_area_order
                )
            ) as expected_filter_group_month,

        from crosswalk
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.state,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.students_dcid,
    e.studentid,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.iep_status,
    e.rn_undergrad,
    e.is_504,
    e.lep_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.gifted_and_talented,
    e.advisory,
    e.grad_iep_exempt_status_overall,
    e.contact_owner_name,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    a.expected_test_academic_year,
    a.expected_test_type,
    a.expected_scope,
    a.expected_score_type,
    a.expected_subject_area,
    a.expected_grade_level,
    a.expected_test_date,
    a.expected_test_month,
    a.expected_test_admin_for_over_time,
    a.expected_field_name,
    a.expected_scope_order,
    a.expected_subject_area_order,
    a.expected_month_order,
    a.expected_admin_order,
    a.expected_filter_group_month,

    s.test_type,
    s.test_date,
    s.test_month,
    s.scope,
    s.subject_area,
    s.course_discipline,
    s.score_type,
    s.scale_score,
    s.previous_total_score_change,
    s.rn_highest,
    s.max_scale_score,
    s.superscore,
    s.running_max_scale_score,
    s.running_superscore,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    additional_fields as a
    on e.academic_year = a.expected_test_academic_year
    and e.grade_level = a.expected_grade_level
left join
    {{ ref("int_assessments__college_assessment") }} as s
    on a.expected_test_academic_year = s.academic_year
    and a.expected_score_type = s.score_type
    and a.expected_test_date = s.test_date
    and e.student_number = s.student_number
where e.school_level = 'HS' and e.rn_year = 1
