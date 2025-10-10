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
    ),,

    attempts as (
        select
            _dbt_source_relation,
            student_number,

            attempt_count_ytd,

            case
                scope
                when 'act_count_ytd'
                then 'ACT'
                when 'sat_count_ytd'
                then 'SAT'
                when 'psatnmsqt_count_ytd'
                then 'PSAT NMSQT'
                when 'psat10_count_ytd'
                then 'PSAT10'
                when 'psat89_count_ytd'
                then 'PSAT 8/9'
            end as scope,

        from
            {{ ref("int_students__college_assessment_participation_roster") }} unpivot (
                attempt_count_ytd for scope in (
                    psat89_count_ytd,
                    psat10_count_ytd,
                    psatnmsqt_count_ytd,
                    sat_count_ytd,
                    act_count_ytd
                )
            )
    ),

    attempts_dedup as (
        select
            _dbt_source_relation,
            student_number,
            scope,

            max(attempt_count_ytd) as attempt_count_ytd,

        from attempts
        group by _dbt_source_relation, student_number, scope
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

            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,

            r.test_type,
            r.scope,
            r.subject_area,
            r.score_type,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r.max_scale_score,
                    p.attempt_count_ytd
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_students__college_assessment_roster") }} as r
            on e.student_number = r.student_number
            and {{ union_dataset_join_clause(left_alias="e", right_alias="r") }}
            and r.test_type is not null
        left join
            attempts_dedup as p
            on e.student_number = p.student_number
            and r.expected_scope = p.scope
            and {{ union_dataset_join_clause(left_alias="e", right_alias="p") }}
            and {{ union_dataset_join_clause(left_alias="r", right_alias="p") }}
        left join
            benchmark_goals as bg
            on r.expected_test_type = bg.expected_test_type
            and r.expected_scope = bg.expected_scope
            and r.expected_score_type = bg.expected_score_type
        where e.school_level = 'HS' and e.rn_year = 1
        group by
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
            r.expected_test_type,
            r.expected_scope,
            r.expected_subject_area,
            r.expected_score_type,
            r.test_type,
            r.scope,
            r.subject_area,
            r.score_type,
            bg.expected_metric_name,
            bg.min_score,
            bg.pct_goal
    )

select *, if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,

from roster
