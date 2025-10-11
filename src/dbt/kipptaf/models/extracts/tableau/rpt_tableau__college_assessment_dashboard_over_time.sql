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

    roster as (
        select
            r._dbt_source_relation,
            r.academic_year,
            r.academic_year_display,
            r.state,
            r.region,
            r.schoolid,
            r.school,
            r.student_number,
            r.students_dcid,
            r.studentid,
            r.salesforce_id,
            r.student_name,
            r.student_first_name,
            r.student_last_name,
            r.grade_level,
            r.student_email,
            r.enroll_status,
            r.iep_status,
            r.rn_undergrad,
            r.is_504,
            r.lep_status,
            r.ktc_cohort,
            r.graduation_year,
            r.year_in_network,
            r.gifted_and_talented,
            r.advisory,
            r.grad_iep_exempt_status_overall,
            r.contact_owner_name,
            r.cumulative_y1_gpa,
            r.cumulative_y1_gpa_projected,
            r.college_match_gpa,
            r.college_match_gpa_bands,
            r.expected_test_academic_year,
            r.expected_test_type,
            r.expected_scope,
            r.expected_score_type,
            r.expected_subject_area,
            r.expected_grade_level,
            r.expected_test_date,
            r.expected_test_month,
            r.expected_test_admin_for_over_time,
            r.expected_field_name,
            r.expected_scope_order,
            r.expected_subject_area_order,
            r.expected_month_order,
            r.expected_admin_order,
            r.expected_filter_group_month,
            r.test_type,
            r.test_date,
            r.test_month,
            r.scope,
            r.subject_area,
            r.course_discipline,
            r.score_type,
            r.scale_score,
            r.previous_total_score_change,
            r.rn_highest,
            r.max_scale_score,
            r.superscore,
            r.running_max_scale_score,
            r.running_superscore,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r.scale_score,
                    p1.attempt_count
                )
            ) as comparison_score,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r.max_scale_score,
                    p2.attempt_count
                )
            ) as max_comparison_score,

        from {{ ref("int_students__college_assessment_roster") }} as r
        left join
            attempts_dedup as p1
            on r.student_number = p1.student_number
            and r.grade_level = p1.grade_level
            and r.expected_scope = p1.scope
            and {{ union_dataset_join_clause(left_alias="r", right_alias="p1") }}
            and p1.attempt_count_type = 'Yearly'
        left join
            attempts_dedup as p2
            on r.student_number = p2.student_number
            and r.expected_scope = p2.scope
            and {{ union_dataset_join_clause(left_alias="r", right_alias="p2") }}
            and p2.attempt_count_type = 'YTD'
        left join
            benchmark_goals as bg
            on r.expected_test_type = bg.expected_test_type
            and r.expected_scope = bg.expected_scope
            and r.expected_score_type = bg.expected_score_type
        group by
            r._dbt_source_relation,
            r.academic_year,
            r.academic_year_display,
            r.state,
            r.region,
            r.schoolid,
            r.school,
            r.student_number,
            r.students_dcid,
            r.studentid,
            r.salesforce_id,
            r.student_name,
            r.student_first_name,
            r.student_last_name,
            r.grade_level,
            r.student_email,
            r.enroll_status,
            r.iep_status,
            r.rn_undergrad,
            r.is_504,
            r.lep_status,
            r.ktc_cohort,
            r.graduation_year,
            r.year_in_network,
            r.gifted_and_talented,
            r.advisory,
            r.grad_iep_exempt_status_overall,
            r.contact_owner_name,
            r.cumulative_y1_gpa,
            r.cumulative_y1_gpa_projected,
            r.college_match_gpa,
            r.college_match_gpa_bands,
            r.expected_test_academic_year,
            r.expected_test_type,
            r.expected_scope,
            r.expected_score_type,
            r.expected_subject_area,
            r.expected_grade_level,
            r.expected_test_date,
            r.expected_test_month,
            r.expected_test_admin_for_over_time,
            r.expected_field_name,
            r.expected_scope_order,
            r.expected_subject_area_order,
            r.expected_month_order,
            r.expected_admin_order,
            r.expected_filter_group_month,
            r.test_type,
            r.test_date,
            r.test_month,
            r.scope,
            r.subject_area,
            r.course_discipline,
            r.score_type,
            r.scale_score,
            r.previous_total_score_change,
            r.rn_highest,
            r.max_scale_score,
            r.superscore,
            r.running_max_scale_score,
            r.running_superscore,
            bg.expected_metric_name,
            bg.min_score,
            bg.pct_goal
    )

select
    *,

    if(comparison_score >= expected_metric_min_score, 1, 0) as met_min_score_int,

    if(
        max_comparison_score >= expected_metric_min_score, 1, 0
    ) as met_min_score_int_overall,

from roster
