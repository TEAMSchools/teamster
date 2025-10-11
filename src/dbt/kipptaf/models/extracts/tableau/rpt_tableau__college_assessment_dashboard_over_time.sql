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

    attempts as (
        select
            _dbt_source_relation,
            student_number,
            attempt_count_ytd as attempt_count,

            null as grade_level,

            'YTD' as attempt_count_type,

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

        union all

        select
            _dbt_source_relation,
            student_number,
            attempt_count,

            grade_level,

            'Yearly' as attempt_count_type,

            case
                scope
                when 'act_count'
                then 'ACT'
                when 'sat_count'
                then 'SAT'
                when 'psatnmsqt_count'
                then 'PSAT NMSQT'
                when 'psat10_count'
                then 'PSAT10'
                when 'psat89_count'
                then 'PSAT 8/9'
            end as scope,

        from
            {{ ref("int_students__college_assessment_participation_roster") }} unpivot (
                attempt_count for scope
                in (psat89_count, psat10_count, psatnmsqt_count, sat_count, act_count)
            )
    ),

    attempts_dedup as (
        select
            _dbt_source_relation,
            student_number,
            scope,
            attempt_count_type,
            grade_level,

            max(attempt_count) as attempt_count,

        from attempts
        group by
            _dbt_source_relation, student_number, scope, attempt_count_type, grade_level
    ),

    max_scores as (
        select
            student_number,
            expected_test_type,
            expected_score_type,

            avg(max_scale_score) as max_scale_score,
            avg(superscore) as superscore,

        from {{ ref("int_students__college_assessment_roster") }}
        group by student_number, expected_test_type, expected_score_type
    ),

    running_scores as (
        select
            student_number,
            expected_test_type,
            expected_score_type,
            expected_test_date,

            avg(running_max_scale_score) as running_max_scale_score,
            avg(running_superscore) as running_superscore,

        from {{ ref("int_students__college_assessment_roster") }}
        group by
            student_number, expected_test_type, expected_score_type, expected_test_date
    ),

    fill_scores as (
        select
            student_number,
            expected_test_type,
            expected_score_type,
            expected_test_date,

            last_value(running_max_scale_score ignore nulls) over (
                partition by student_number, expected_test_type, expected_score_type
                order by expected_test_date
            ) as running_max_scale_score,

            last_value(running_superscore ignore nulls) over (
                partition by student_number, expected_test_type, expected_score_type
                order by expected_test_date
            ) as running_superscore,

        from running_scores
    ),

    roster as (
        select
            r1._dbt_source_relation,
            r1.academic_year,
            r1.academic_year_display,
            r1.state,
            r1.region,
            r1.schoolid,
            r1.school,
            r1.student_number,
            r1.students_dcid,
            r1.studentid,
            r1.salesforce_id,
            r1.student_name,
            r1.student_first_name,
            r1.student_last_name,
            r1.grade_level,
            r1.student_email,
            r1.enroll_status,
            r1.iep_status,
            r1.rn_undergrad,
            r1.is_504,
            r1.lep_status,
            r1.ktc_cohort,
            r1.graduation_year,
            r1.year_in_network,
            r1.gifted_and_talented,
            r1.advisory,
            r1.grad_iep_exempt_status_overall,
            r1.contact_owner_name,
            r1.cumulative_y1_gpa,
            r1.cumulative_y1_gpa_projected,
            r1.college_match_gpa,
            r1.college_match_gpa_bands,
            r1.expected_test_academic_year,
            r1.expected_test_type,
            r1.expected_scope,
            r1.expected_score_type,
            r1.expected_subject_area,
            r1.expected_grade_level,
            r1.expected_test_date,
            r1.expected_test_month,
            r1.expected_test_admin_for_over_time,
            r1.expected_field_name,
            r1.expected_scope_order,
            r1.expected_subject_area_order,
            r1.expected_month_order,
            r1.expected_admin_order,
            r1.expected_filter_group_month,
            r1.test_type,
            r1.test_date,
            r1.test_month,
            r1.scope,
            r1.subject_area,
            r1.course_discipline,
            r1.score_type,
            r1.scale_score,
            r1.previous_total_score_change,
            r1.rn_highest,

            r2.max_scale_score,
            r2.superscore,

            r3.running_max_scale_score,
            r3.running_superscore,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r1.scale_score,
                    p1.attempt_count
                )
            ) as comparison_score,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r3.running_max_scale_score,
                    p2.attempt_count
                )
            ) as running_max_comparison_score,

        from {{ ref("int_students__college_assessment_roster") }} as r1
        left join
            max_scores as r2
            on r1.student_number = r2.student_number
            and r1.expected_test_type = r2.expected_test_type
            and r1.expected_score_type = r2.expected_score_type
        left join
            fill_scores as r3
            on r1.student_number = r3.student_number
            and r1.expected_test_type = r3.expected_test_type
            and r1.expected_score_type = r3.expected_score_type
            and r1.expected_test_date = r3.expected_test_date
        left join
            attempts_dedup as p1
            on r1.student_number = p1.student_number
            and r1.grade_level = p1.grade_level
            and r1.expected_scope = p1.scope
            and {{ union_dataset_join_clause(left_alias="r1", right_alias="p1") }}
            and p1.attempt_count_type = 'Yearly'
        left join
            attempts_dedup as p2
            on r1.student_number = p2.student_number
            and r1.expected_scope = p2.scope
            and {{ union_dataset_join_clause(left_alias="r1", right_alias="p2") }}
            and p2.attempt_count_type = 'YTD'
        left join
            benchmark_goals as bg
            on r1.expected_test_type = bg.expected_test_type
            and r1.expected_scope = bg.expected_scope
            and r1.expected_score_type = bg.expected_score_type
        group by
            r1._dbt_source_relation,
            r1.academic_year,
            r1.academic_year_display,
            r1.state,
            r1.region,
            r1.schoolid,
            r1.school,
            r1.student_number,
            r1.students_dcid,
            r1.studentid,
            r1.salesforce_id,
            r1.student_name,
            r1.student_first_name,
            r1.student_last_name,
            r1.grade_level,
            r1.student_email,
            r1.enroll_status,
            r1.iep_status,
            r1.rn_undergrad,
            r1.is_504,
            r1.lep_status,
            r1.ktc_cohort,
            r1.graduation_year,
            r1.year_in_network,
            r1.gifted_and_talented,
            r1.advisory,
            r1.grad_iep_exempt_status_overall,
            r1.contact_owner_name,
            r1.cumulative_y1_gpa,
            r1.cumulative_y1_gpa_projected,
            r1.college_match_gpa,
            r1.college_match_gpa_bands,
            r1.expected_test_academic_year,
            r1.expected_test_type,
            r1.expected_scope,
            r1.expected_score_type,
            r1.expected_subject_area,
            r1.expected_grade_level,
            r1.expected_test_date,
            r1.expected_test_month,
            r1.expected_test_admin_for_over_time,
            r1.expected_field_name,
            r1.expected_scope_order,
            r1.expected_subject_area_order,
            r1.expected_month_order,
            r1.expected_admin_order,
            r1.expected_filter_group_month,
            r1.test_type,
            r1.test_date,
            r1.test_month,
            r1.scope,
            r1.subject_area,
            r1.course_discipline,
            r1.score_type,
            r1.scale_score,
            r1.previous_total_score_change,
            r1.rn_highest,
            r2.max_scale_score,
            r2.superscore,
            r3.running_max_scale_score,
            r3.running_superscore,
            bg.expected_metric_name,
            bg.min_score,
            bg.pct_goal
    )

select
    *,

    if(comparison_score >= expected_metric_min_score, 1, 0) as met_min_score_int_yearly,

    if(
        running_max_comparison_score >= expected_metric_min_score, 1, 0
    ) as met_min_score_int_running,

    max(if(max_scale_score >= expected_metric_min_score, 1, 0)) over (
        partition by
            student_number,
            expected_test_type,
            expected_score_type,
            expected_metric_name
        order by expected_test_date
    ) as met_min_score_int_overall,

    max(if(max_scale_score >= expected_metric_min_score, 1, 0)) over (
        partition by student_number, expected_test_type, expected_metric_name
        order by expected_test_date
    ) as met_min_score_int_act_or_sat_overall,

from roster
