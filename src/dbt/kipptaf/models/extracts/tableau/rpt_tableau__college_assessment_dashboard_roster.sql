with
    expected_admins as (
        select
            expected_region,
            expected_grade_level,
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_admin_season,
            expected_month,
            expected_grouping,
            expected_field_name,

            'foo' as bar,

        from {{ ref("stg_google_sheets__kippfwd_expected_assessments") }}
    ),

    focus_scores as (
        select
            e.region,
            e.student_number,
            e.grade_level,

            a.expected_test_type,
            a.expected_scope,
            a.expected_score_type,
            a.expected_admin_season,
            a.expected_month,
            a.expected_grouping,
            a.expected_field_name,

            s.test_type,
            s.scope,
            s.score_type,
            s.test_date,
            s.test_month,
            s.scale_score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            expected_admins as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
        left join
            {{ ref("int_assessments__college_assessment") }} as s
            and a.expected_score_type = s.score_type
            and a.expected_month = s.test_month
            and a.expected_region = e.region
            and a.expected_grade_level = e.grade_level
        where
            e.school_level = 'HS'
            and e.rn_year = 1
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    )

select *
from
    focus_scores as s
    -- left join
    -- expected_admins as e on 'foo' = s.bar
    {# ,


    scores as (
        select
            *,

            concat(
                field_name, ' ', score_category
            ) as expected_field_name_score_category,

            concat(
                scope, ' ', subject_area, ' ', score_category
            ) as expected_filter_group,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "test_type",
                        "score_type",
                        "test_date",
                    ]
                )
            }} as unique_test_admin_id,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    previous_total_score_change as 'Previous Total Score Change'
                )
            )
        where graduation_year >= {{ var("current_academic_year") + 1 }}
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
    ea.expected_score_category,
    ea.expected_field_name_score_category,
    ea.expected_filter_group,
    ea.expected_admin_order,

    s.sat_combined_superscore,
    s.sat_ebrw_highest,
    s.sat_math_highest,

    a.score,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    expected_admins as ea
    on 'foo' = ea.bar
    and ea.expected_score_category in ('Scale Score', 'Previous Total Score Change')
    and ea.filter_group
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
#}
    
