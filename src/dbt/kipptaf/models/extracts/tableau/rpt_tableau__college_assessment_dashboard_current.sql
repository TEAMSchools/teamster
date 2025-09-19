{% set comparison_benchmarks = [
    {"label": "College-Ready", "prefix": "college_ready"},
    {"label": "HS-Ready", "prefix": "hs_ready"},
] %}

with
    benchmark_goals as (
        select
            expected_test_type,
            expected_scope,
            expected_score_type,
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
        where expected_test_type = 'Official' and goal_type = 'Benchmark'
        group by
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area
    ),

    unpivot_data as (
        select
            academic_year,
            student_number,

            administration_round,
            test_type,
            test_date,
            test_month,
            scope,
            subject_area,
            score_type,
            test_admin_for_over_time,

            score_category,
            score,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    running_max_scale_score as 'Running Max Scale Score',
                    running_superscore as 'Running Superscore'
                )
            )
    ),

    metrics as (
        select
            e.academic_year,
            e.student_number,
            e.administration_round,
            e.test_type,
            e.test_date,
            e.test_month,
            e.scope,
            e.subject_area,
            e.score_type,
            e.test_admin_for_over_time,
            e.score_category,
            e.score,

            metric_name,

        from unpivot_data as e
        cross join unnest(['HS-Ready', 'College-Ready']) as metric_name
    ),

    goals_check as (
        select
            e.*,

            case
                e.metric_name
                when 'HS-Ready'
                then bg.hs_ready_min_score
                when 'College-Ready'
                then bg.college_ready_min_score
            end as metric_min_score,

            case
                e.metric_name
                when 'HS-Ready'
                then bg.hs_ready_pct_goal
                when 'College-Ready'
                then bg.college_ready_pct_goal
            end as metric_pct_goal,

        from metrics as e
        left join
            benchmark_goals as bg
            on e.test_type = bg.expected_test_type
            and e.scope = bg.expected_scope
            and e.subject_area = bg.expected_subject_area
    )

select
    e.academic_year,
    e.academic_year_display,
    e.state,
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

    g.academic_year as test_academic_year,
    g.administration_round,
    g.test_type,
    g.test_date,
    g.test_month,
    g.scope,
    g.subject_area,
    g.score_type,
    g.test_admin_for_over_time,
    g.score_category,
    g.score,
    g.metric_name,
    g.metric_min_score,
    g.metric_pct_goal,

    if(g.score >= g.metric_min_score, 1, 0) as met_min_score_int,
    if(g.metric_min_score is not null, 1, 0) as denominator_int,

from {{ ref("int_extracts__student_enrollments") }} as e
left join goals_check as g on e.student_number = g.student_number
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.school_level = 'HS'
    and e.rn_year = 1
