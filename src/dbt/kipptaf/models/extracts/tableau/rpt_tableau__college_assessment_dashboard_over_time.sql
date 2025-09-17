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
                    case when goal_subtype = '{{ benchmark.label }}' then min_score end
                ) as {{ benchmark.prefix }}_min_score,
                avg(
                    case when goal_subtype = '{{ benchmark.label }}' then pct_goal end
                ) as {{ benchmark.prefix }}_pct_goal
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
    e.grade_level,
    e.enroll_status,
    e.iep_status,
    e.is_504,
    e.grad_iep_exempt_status_overall,
    e.lep_status,
    e.ktc_cohort,
    e.graduation_year,
    e.year_in_network,
    e.college_match_gpa_bands,
    e.administration_round,
    e.test_type,
    e.test_date,
    e.test_month,
    e.scope,
    e.subject_area,
    e.score_type,
    e.scale_score,
    e.max_scale_score,
    e.superscore,
    e.running_max_scale_score,
    e.running_superscore,

    metrics,

    case
        metrics
        when 'HS-Ready'
        then bg.hs_ready_min_score
        when 'College-Ready'
        then bg.college_ready_min_score
    end as metric_min_score,

    case
        metrics
        when 'HS-Ready'
        then bg.hs_ready_pct_goal
        when 'College-Ready'
        then bg.college_ready_pct_goal
    end as metric_pct_goal,

from {{ ref("int_students__college_assessment_roster") }} as e
cross join unnest(['HS-Ready', 'College-Ready']) as metrics
left join
    benchmark_goals as bg
    on e.test_type = bg.expected_test_type
    and e.scope = bg.expected_scope
    and e.subject_area = bg.expected_subject_area
