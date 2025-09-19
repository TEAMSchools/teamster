with
    benchmark_goals as (
        select
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            goal_subtype,
            min_score,
            pct_goal,

            goal_subtype as expected_metric_name,

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where expected_test_type = 'Official' and goal_type = 'Benchmark'

        union all

        select
            expected_test_type,
            expected_scope,
            expected_score_type,
            expected_subject_area,
            goal_category as goal_subtype,
            min_score,
            pct_goal,

            concat(expected_scope, ' ', goal_category) as expected_metric_name,

        from {{ ref("stg_google_sheets__kippfwd_goals") }}
        where expected_test_type = 'Official' and goal_type = 'Attempts'
    ),

    expected_admin_metrics as (
        -- need a distinct list of possible scores and their categories
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

            'foo' as bar,

            expected_metric_name,

            expected_score_category,

            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

        from {{ ref("int_students__college_assessment_roster") }} as r
        cross join
            unnest(
                [
                    'HS-Ready',
                    'College-Ready',
                    'ACT Group 1',
                    'ACT Group 2+',
                    'SAT Group 1',
                    'SAT Group 2+',
                    'PSAT NMSQT Group 1',
                    'PSAT NMSQT Group 2+',
                    'PSAT10 Group 1',
                    'PSAT10 Group 2+',
                    'PSAT 8/9 Group 1',
                    'PSAT 8/9 Group 2+'
                ]
            ) as expected_metric_name
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
            and expected_metric_name = bg.expected_metric_name
    ),

    scores as (
        select
            academic_year,
            surrogate_key,
            student_number,
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
    ),

    roster as (
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

            ea.expected_test_academic_year,
            ea.expected_test_type,
            ea.expected_test_date,
            ea.expected_test_month,
            ea.expected_scope,
            ea.expected_subject_area,
            ea.expected_score_type,
            ea.expected_grade_level,
            ea.expected_test_admin_for_over_time,
            ea.expected_metric_name,
            ea.expected_score_category,
            ea.expected_metric_min_score,
            ea.expected_metric_pct_goal,

            s.test_type,
            s.test_date,
            s.test_month,
            s.scope,
            s.subject_area,
            s.score_type,
            s.score_category,
            s.score,

            if(s.score >= ea.expected_metric_min_score, 1, 0) as met_min_score_int,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join expected_admin_metrics as ea on 'foo' = ea.bar
        left join
            scores as s
            on e.student_number = s.student_number
            and ea.surrogate_key = s.surrogate_key
            and ea.expected_score_category = s.score_category
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
    )

select
    *,

    max(met_min_score_int) over (
        partition by
            student_number,
            expected_score_type,
            expected_metric_name,
            expected_score_category
        order by expected_test_date
    ) as running_met_min_score,

from roster
