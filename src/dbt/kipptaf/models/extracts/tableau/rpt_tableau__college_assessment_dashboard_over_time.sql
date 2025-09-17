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

    unpivot_data as (
        select
            academic_year,
            academic_year_display,
            state,
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
            e.academic_year_display,
            state,
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
    ),

    met_min_score as (
        select
            academic_year,
            academic_year_display,
            state,
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
            metric_name,
            metric_min_score,
            metric_pct_goal,

            if(score >= metric_min_score, 1, 0) as met_min_score_int,
            if(metric_min_score is not null, 1, 0) as denominator_int,

        from goals_check
    )

select
    state,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name,

    'State' as grouping_level,

    avg(metric_min_score) as metric_min_score,
    avg(metric_pct_goal) as metric_pct_goal,
    sum(met_min_score_int) as total_students_met,
    sum(denominator_int) total_students,

from met_min_score
group by
    state,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name

union all

select
    region,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name,

    'Region' as grouping_level,

    avg(metric_min_score) as metric_min_score,
    avg(metric_pct_goal) as metric_pct_goal,
    sum(met_min_score_int) as total_students_met,
    sum(denominator_int) total_students,

from met_min_score
group by
    region,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name

union all

select
    school,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name,

    'School' as grouping_level,

    avg(metric_min_score) as metric_min_score,
    avg(metric_pct_goal) as metric_pct_goal,
    sum(met_min_score_int) as total_students_met,
    sum(denominator_int) total_students,

from met_min_score
group by
    school,
    graduation_year,
    test_type,
    scope,
    subject_area,
    score_type,
    test_admin_for_over_time,
    metric_name
