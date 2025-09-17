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
    ),

    metrics_unpivot as (
        select
            academic_year,
            academic_year_display,
            region,
            schoolid,
            school,
            student_number,
            grade_level,
            enroll_status,
            iep_status,
            is_504,
            grad_iep_exempt_status_overall,
            lep_status,
            ktc_cohort,
            graduation_year,
            year_in_network,
            college_match_gpa_bands,
            administration_round,
            test_type,
            test_date,
            test_month,
            scope,
            subject_area,
            score_type,
            score_category,
            score,

            metric_name,

            case
                metric_name
                when 'HS-Ready'
                then bg.hs_ready_min_score
                when 'College-Ready'
                then bg.college_ready_min_score
            end as metric_min_score,

            case
                metric_name
                when 'HS-Ready'
                then bg.hs_ready_pct_goal
                when 'College-Ready'
                then bg.college_ready_pct_goal
            end as metric_pct_goal,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    running_max_scale_score as 'Running Max Scale Score',
                    running_superscore as 'Running Superscore'
                )
            ) as e
        cross join unnest(['HS-Ready', 'College-Ready']) as metric_name
        left join
            benchmark_goals as bg
            on e.test_type = bg.expected_test_type
            and e.scope = bg.expected_scope
            and e.subject_area = bg.expected_subject_area
    )

select
    academic_year,
    academic_year_display,
    region,
    schoolid,
    school,
    student_number,
    grade_level,
    enroll_status,
    iep_status,
    is_504,
    grad_iep_exempt_status_overall,
    lep_status,
    ktc_cohort,
    graduation_year,
    year_in_network,
    college_match_gpa_bands,
    administration_round,
    test_type,
    test_date,
    test_month,
    scope,
    subject_area,
    score_type,
    score_category,
    score,
    metric_name,
    metric_min_score,
    metric_pct_goal,

    if(score >= metric_min_score, 1, 0) as met_min_score_int,
    if(metric_min_score is not null, 1, 0) as denominator_int,

from metrics_unpivot
