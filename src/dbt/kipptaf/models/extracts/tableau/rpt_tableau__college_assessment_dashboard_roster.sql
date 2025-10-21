with
    expected_admins as (
        select
            expected_region,
            expected_grade_level,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_admin_season,
            expected_admin_season_order,
            expected_month,
            expected_grouping,
            expected_field_name,

            expected_score_category,

            'foo' as bar,

            concat(
                expected_field_name, ' ', expected_score_category
            ) as expected_field_name_score_category,

            concat(
                expected_scope, ' ', expected_grouping, ' ', expected_score_category
            ) as expected_filter_group,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "expected_test_type",
                        "expected_score_type",
                        "expected_admin_season",
                    ]
                )
            }} as expected_unique_test_admin_id,

        from {{ ref("stg_google_sheets__kippfwd_expected_assessments") }}
        cross join
            unnest(
                [
                    'Scale Score',
                    'Max Scale Score',
                    'Superscore',
                    'Previous Total Score Change'
                ]
            ) as expected_score_category
    ),

    scores as (
        select
            *,

            concat(
                expected_field_name, ' ', score_category
            ) as expected_field_name_score_category,

            concat(
                expected_scope, ' ', expected_grouping, ' ', score_category
            ) as expected_filter_group,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "expected_test_type",
                        "expected_score_type",
                        "expected_admin_season",
                    ]
                )
            }} as unique_test_admin_id,

        from
            {{ ref("int_tableau__college_assessment_roster_scores") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    previous_total_score_change as 'Previous Total Score Change'
                )
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
    ea.expected_grouping,
    ea.expected_grade_level,
    ea.expected_admin_season,
    ea.expected_month,
    ea.expected_field_name,
    ea.expected_score_category,
    ea.expected_field_name_score_category,
    ea.expected_filter_group,
    ea.expected_admin_season_order,

    s.sat_combined_superscore,
    s.sat_ebrw_highest,
    s.sat_math_highest,

    a.score,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    expected_admins as ea
    on 'foo' = ea.bar
    and ea.expected_score_category in ('Scale Score', 'Previous Total Score Change')
    and ea.expected_filter_group
    not in ('Math_Previous Total Score Change', 'EBRW_Previous Total Score Change')
left join superscores_dedup as s on e.student_number = s.student_number
left join
    scores as a
    on e.student_number = a.student_number
    and ea.expected_unique_test_admin_id = a.unique_test_admin_id
    and ea.expected_score_category = a.score_category
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
