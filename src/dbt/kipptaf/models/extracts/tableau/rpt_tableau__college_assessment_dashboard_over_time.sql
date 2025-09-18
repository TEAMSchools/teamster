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

    unpivot_scores as (
        select
            academic_year,
            student_number,
            grade_level,
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

    expected_admins as (
        -- need a distinct list of possible tests to force rows on the main select
        select distinct
            grade_level, score_type, test_admin_for_over_time as expected_admin,

        from unpivot_scores
    ),

    admin_metrics_scaffold as (
        select e.grade_level, e.score_type, e.expected_admin, metric_name,

        from expected_admins as e
        cross join unnest(['HS-Ready', 'College-Ready']) as metric_name
    ),

    base_roster as (
        /* open to a better way of doing this: i need to force rows for all possible
           tests anyone has ever taken */
        select distinct
            g.academic_year,
            g.academic_year_display,
            g.state,
            g.region,
            g.schoolid,
            g.school,
            g.student_number,
            g.grade_level,
            g.enroll_status,
            g.iep_status,
            g.is_504,
            g.grad_iep_exempt_status_overall,
            g.lep_status,
            g.ktc_cohort,
            g.graduation_year,
            g.year_in_network,

            a.expected_admin,
            a.metric_name,

        from {{ ref("int_students__college_assessment_roster") }} as g
        inner join admin_metrics_scaffold as a on g.grade_level = a.grade_level
    ),

    roster_and_scores as (
        select
            b.academic_year,
            b.academic_year_display,
            b.state,
            b.region,
            b.schoolid,
            b.school,
            b.student_number,
            b.grade_level,
            b.enroll_status,
            b.iep_status,
            b.is_504,
            b.grad_iep_exempt_status_overall,
            b.lep_status,
            b.ktc_cohort,
            b.graduation_year,
            b.year_in_network,
            b.expected_admin,
            b.metric_name,

            u.administration_round,
            u.test_type,
            u.test_date,
            u.test_month,
            u.scope,
            u.subject_area,
            u.score_type,
            u.test_admin_for_over_time,
            u.score_category,
            u.score,

            case
                b.metric_name
                when 'HS-Ready'
                then bg.hs_ready_min_score
                when 'College-Ready'
                then bg.college_ready_min_score
            end as metric_min_score,

            case
                b.metric_name
                when 'HS-Ready'
                then bg.hs_ready_pct_goal
                when 'College-Ready'
                then bg.college_ready_pct_goal
            end as metric_pct_goal,

        from base_roster as b
        left join
            unpivot_scores as u
            on b.academic_year = u.academic_year
            and b.student_number = u.student_number
            and b.expected_admin = u.test_admin_for_over_time
        left join
            benchmark_goals as bg
            on u.test_type = bg.expected_test_type
            and u.score_type = bg.expected_score_type
    )

select *, if(score >= metric_min_score, 1, 0) as met_min_score_int,

from roster_and_scores
