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

    expected_admin_metrics as (
        -- create a list of all possible scores
        select distinct
            r.surrogate_key,
            r.expected_test_academic_year,
            r.expected_test_type,
            r.expected_test_date,
            r.expected_test_month,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
            r.expected_grade_level,
            r.expected_test_admin_for_over_time,
            r.expected_admin_order,

            expected_metric_name,

            expected_score_category,

            case
                expected_metric_name
                when 'HS-Ready'
                then bg.hs_ready_min_score
                when 'College-Ready'
                then bg.college_ready_min_score
            end as expected_metric_min_score,

            case
                expected_metric_name
                when 'HS-Ready'
                then bg.hs_ready_pct_goal
                when 'College-Ready'
                then bg.college_ready_pct_goal
            end as expected_metric_pct_goal,

        from {{ ref("int_students__college_assessment_roster") }} as r
        cross join unnest(['HS-Ready', 'College-Ready']) as expected_metric_name
        cross join
            unnest(
                [
                    'Scale Score',
                    'Max Scale Score',
                    'Superscore',
                    'Running Max Scale Score',
                    'Running Superscore'
                ]
            ) as expected_score_category
        -- must be left join because not all score types have goals
        left join
            benchmark_goals as bg
            on r.expected_test_type = bg.expected_test_type
            and r.expected_scope = bg.expected_scope
            and r.expected_score_type = bg.expected_score_type
    ),

    scores as (
        select
            academic_year,
            surrogate_key,
            student_number,
            grade_level,
            test_type,
            test_date,
            test_month,
            scope,
            subject_area,
            score_type,

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
    )

select
    r.academic_year,
    r.academic_year_display,
    r.state,
    r.region,
    r.schoolid,
    r.school,
    r.student_number,
    r.grade_level,
    r.enroll_status,
    r.iep_status,
    r.is_504,
    r.grad_iep_exempt_status_overall,
    r.lep_status,
    r.ktc_cohort,
    r.graduation_year,
    r.year_in_network,

    ea.expected_test_academic_year,
    ea.expected_test_type,
    ea.expected_test_date,
    ea.expected_test_month,
    ea.expected_scope,
    ea.expected_subject_area,
    ea.expected_score_type,
    ea.expected_grade_level,
    ea.expected_test_admin_for_over_time,
    ea.expected_admin_order,
    ea.expected_metric_name,
    ea.expected_score_category,
    ea.expected_metric_min_score,
    ea.expected_metric_pct_goal,

    u.test_type,
    u.test_date,
    u.test_month,
    u.scope,
    u.subject_area,
    u.score_type,
    u.score_category,
    u.score,

    if(u.score >= ea.expected_metric_min_score, 1, 0) as met_min_score_int,

    max(if(u.score >= ea.expected_metric_min_score, 1, 0)) over (
        partition by
            r.student_number,
            ea.expected_score_type,
            ea.expected_metric_name,
            ea.expected_score_category
        order by ea.expected_test_date
    ) as running_met_min_score,

from {{ ref("int_students__college_assessment_roster") }} as r
inner join expected_admin_metrics as ea on r.grade_level = ea.expected_grade_level
left join
    scores as u
    on r.student_number = u.student_number
    and ea.surrogate_key = u.surrogate_key
    and ea.expected_score_category = u.score_category
