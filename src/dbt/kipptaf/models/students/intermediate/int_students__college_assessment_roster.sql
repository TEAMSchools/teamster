with
    roster as (
        select
            s.academic_year,
            s.student_number,
            s.test_type,
            s.scope,
            s.subject_area,
            s.course_discipline,
            s.score_type,
            s.administration_round,
            s.test_date,
            s.test_month,
            s.scale_score,
            s.rn_highest,
            s.max_scale_score,
            s.running_max_scale_score,
            s.previous_total_score_change,
            s.superscore,
            s.running_superscore,

            e.grade_level,
            e.graduation_year,
            e.salesforce_id,

            concat(
                'G',
                grade_level,
                ' ',
                test_month,
                ' ',
                scope,
                ' ',
                test_type,
                ' ',
                subject_area
            ) as field_name,

            unix_date(s.test_date) as date_order,

            case
                s.scope
                when 'SAT'
                then 5
                when 'ACT'
                then 4
                when 'PSAT NMSQT'
                then 3
                when 'PSAT10'
                then 2
                when 'PSAT 8/9'
                then 1
            end as scope_order,

            case
                when s.subject_area = 'Combined'
                then 3
                when s.subject_area = 'Composite'
                then 5
                when s.subject_area = 'EBRW'
                then 2
                when s.subject_area = 'Science'
                then 1
                when s.subject_area = 'English'
                then 2
                when s.subject_area = 'Reading'
                then 4
                when concat(s.scope, s.subject_area) = 'ACTMath'
                then 3
                else 1
            end as subject_area_order,

            if(
                s.subject_area in ('Composite', 'Combined'), 'Total', s.subject_area
            ) as aligned_subject_area,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "s.student_number",
                        "s.test_type",
                        "s.score_type",
                        "s.test_date",
                    ]
                )
            }} as surrogate_key,

        from {{ ref("int_assessments__college_assessment") }} as s
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on s.academic_year = e.academic_year
            and s.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            s.score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    )

select
    * except (scope_order, date_order, subject_area_order),

    concat(scope_order, date_order, subject_area_order) as expected_admin_order,

from roster
