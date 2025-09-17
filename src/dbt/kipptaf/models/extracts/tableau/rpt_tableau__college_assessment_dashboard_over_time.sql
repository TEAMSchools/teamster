{% set comparison_benchmarks = [
    {"label": "College-Ready", "prefix": "college_ready"},
    {"label": "HS-Ready", "prefix": "hs_ready"},
] %}

with
    benchmark_goals as (
        select
            expected_test_type,
            expected_scope,
            expected_subject_area,

            {% for benchmark in comparison_benchmarks %}
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then score end
                ) as {{ benchmark.prefix }}_min_score,
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then goal end
                ) as {{ benchmark.prefix }}_goal
                {% if not loop.last %},{% endif %}
            {% endfor %}

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where
            expected_test_type = 'Official'
            and goal_type = 'Benchmark'
            and expected_subject_area in ('Composite', 'Combined')
        group by expected_test_type, expected_scope, expected_subject_area
    )

select
    e.academic_year,
    e.academic_year_display,
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.enroll_status,
    e.cohort,
    e.iep_status,
    e.is_504,
    e.grad_iep_exempt_status_overall,
    e.lep_status,
    e.gifted_and_talented,
    e.advisory,
    e.student_email,
    e.rn_undergrad,
    e.salesforce_id,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.contact_owner_name,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_unweighted,
    e.cumulative_y1_gpa_projected,
    e.cumulative_y1_gpa_projected_s1,
    e.cumulative_y1_gpa_projected_s1_unweighted,
    e.core_cumulative_y1_gpa,
    e.administration_round,
    e.test_type,
    e.test_date,
    e.test_month,
    e.scope,
    e.subject_area,
    e.course_discipline,
    e.score_type,
    e.scale_score,
    e.previous_total_score_change,
    e.rn_highest,
    e.max_scale_score,
    e.superscore,
    e.running_max_scale_score,
    e.running_superscore,

    bg.hs_ready_min_score,
    bg.college_ready_min_score,
    bg.hs_ready_goal,
    bg.college_ready_goal,

from {{ ref("int_students__college_assessment_roster") }} as e
left join
    benchmark_goals as bg
    on e.test_type = bg.expected_test_type
    and e.scope = bg.expected_scope
    and e.subject_area = bg.expected_subject_area
