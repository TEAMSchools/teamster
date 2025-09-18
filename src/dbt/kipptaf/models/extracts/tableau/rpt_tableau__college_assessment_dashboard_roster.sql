with
    scores as (
        select
            region,
            schoolid,
            school,
            student_number,
            salesforce_id,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            student_email,
            enroll_status,
            ktc_cohort,
            graduation_year,
            year_in_network,
            iep_status,
            grad_iep_exempt_status_overall,
            cumulative_y1_gpa,
            cumulative_y1_gpa_projected,
            college_match_gpa,
            college_match_gpa_bands,

            test_type,
            test_admin_for_roster,
            test_admin_for_over_time,
            scope,
            subject_area,
            score_type,
            test_date,
            test_month,
            month_order,

            score_category,
            score,

            concat(scope, ' ', subject_area, ' ', score_category) as filter_group,

            concat(
                grade_level,
                ' ',
                month_order,
                ' ',
                scope,
                ' ',
                test_month,
                ' ',
                subject_area,
                ' ',
                score_category
            ) as filter_group_month,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    previous_total_score_change as 'Previous Total Score Change'
                )
            )
        where
            rn_undergrad = 1
            and graduation_year = {{ var("current_academic_year") + 1 }}
    ),

    filter_superscores as (
        select student_number, filter_group, avg(score) as score,

        from scores
        where
            filter_group in (
                'SAT Combined Superscore',
                'SAT EBRW Max Scale Score',
                'SAT Math Max Scale Score'
            )
        group by student_number, filter_group
    ),

    superscores as (
        select
            student_number, sat_combined_superscore, sat_ebrw_highest, sat_math_highest,

        from
            filter_superscores pivot (
                avg(score) for filter_group in (
                    'SAT Combined Superscore' as sat_combined_superscore,
                    'SAT EBRW Max Scale Score' as sat_ebrw_highest,
                    'SAT Math Max Scale Score' as sat_math_highest
                )
            )
    )

select *,
from superscores
