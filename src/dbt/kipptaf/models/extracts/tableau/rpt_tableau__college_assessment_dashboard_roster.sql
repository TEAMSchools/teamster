with
    scores as (
        select
            *,

            concat(
                expected_field_name, ' ', expected_score_category
            ) as expected_field_name_score_category,

            concat(
                expected_scope, ' ', expected_subject_area, ' ', expected_score_category
            ) as expected_filter_group,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for expected_score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    previous_total_score_change as 'Previous Total Score Change'
                )
            )
        where
            graduation_year = {{ var("current_academic_year") + 1 }} and scope != 'ACT'
    ),

    expected_admins as (
        -- need a distinct list of possible tests to force rows on the main select
        select distinct
            surrogate_key,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            expected_grade_level,
            expected_test_date,
            expected_test_month,
            expected_field_name,
            expected_admin_order,
            expected_filter_group_month,
            expected_score_category,
            expected_field_name_score_category,
            expected_filter_group,

            'foo' as bar,

        from scores
        where
            expected_filter_group in (
                'SAT Combined Scale Score',
                'SAT Combined Previous Total Score Change',
                'SAT EBRW Scale Score',
                'SAT Math Scale Score',
                'PSAT NMSQT Combined Scale Score',
                'PSAT NMSQT Combined Previous Total Score Change',
                'PSAT NMSQT EBRW Scale Score',
                'PSAT NMSQT Math Scale Score',
                'PSAT10 Combined Scale Score',
                'PSAT10 Combined Previous Total Score Change',
                'PSAT10 EBRW Scale Score',
                'PSAT10 Math Scale Score'
            )
    ),

    superscores as (
        select
            student_number, sat_combined_superscore, sat_ebrw_highest, sat_math_highest,

        from
            scores pivot (
                avg(score) for expected_filter_group in (
                    'SAT Combined Superscore' as sat_combined_superscore,
                    'SAT EBRW Max Scale Score' as sat_ebrw_highest,
                    'SAT Math Max Scale Score' as sat_math_highest
                )
            )
    ),

    superscores_dedup as (
        select
            student_number,

            avg(sat_combined_superscore) as sat_combined_superscore,
            avg(sat_ebrw_highest) as sat_ebrw_highest,
            avg(sat_math_highest) as sat_math_highest,

        from superscores
        group by student_number
    )

select
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.iep_status,
    e.grad_iep_exempt_status_overall,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    ea.expected_test_type,
    ea.expected_scope,
    ea.expected_score_type,
    ea.expected_subject_area,
    ea.expected_grade_level,
    ea.expected_test_date,
    ea.expected_test_month,
    ea.expected_field_name,
    ea.expected_admin_order,
    ea.expected_filter_group_month,
    ea.expected_score_category,
    ea.expected_field_name_score_category,
    ea.expected_filter_group,

    s.sat_combined_superscore,
    s.sat_ebrw_highest,
    s.sat_math_highest,

    a.score,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join expected_admins as ea on 'foo' = ea.bar
left join superscores_dedup as s on e.student_number = s.student_number
left join
    scores as a
    on e.student_number = a.student_number
    and ea.surrogate_key = a.surrogate_key
    and ea.expected_score_category = a.expected_score_category
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year = {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
