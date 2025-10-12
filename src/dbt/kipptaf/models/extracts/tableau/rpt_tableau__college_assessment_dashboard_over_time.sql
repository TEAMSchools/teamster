with
    strategy as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            a.academic_year as expected_test_academic_year,
            a.test_type as expected_test_type,
            a.test_date as expected_test_date,
            a.test_month as expected_test_month,
            a.scope as expected_scope,
            a.subject_area as expected_subject_area,
            a.score_type as expected_score_type,

            e.graduation_year as expected_graduation_year,

        from {{ ref("int_assessments__college_assessment") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            a.score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    strategy_attempts_ytd as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            a.academic_year as expected_test_academic_year,
            a.test_type as expected_test_type,
            a.test_date as expected_test_date,
            a.test_month as expected_test_month,
            a.scope as expected_scope,
            a.subject_area as expected_subject_area,
            a.score_type as expected_score_type,

            e.graduation_year as expected_graduation_year,

        from {{ ref("int_assessments__college_assessment") }} as a
        inner join
            {{ ref("int_extracts__student_enrollments") }} as e
            on a.academic_year = e.academic_year
            and a.student_number = e.student_number
            and e.school_level = 'HS'
            and e.rn_year = 1
        where
            a.score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psatnmsqt_total',
                'psat10_total'
            )
    ),

    base_rows_attempts_ytd as (
        select
            e.academic_year,
            e.student_number,
            e.studentid,
            e.students_dcid,
            e.salesforce_id,
            e.graduation_year,

            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_test_date,

            t.test_type,
            t.scope,
            t.score_type,

            count(concat(t.test_type, t.scope)) over (
                partition by e.student_number, s.expected_test_type, s.expected_scope
                order by s.expected_test_date
            ) as test_count_running,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            strategy_attempts_ytd as s
            on e.academic_year = s.expected_test_academic_year
            and e.graduation_year = s.expected_graduation_year
        left join
            {{ ref("int_students__college_assessment_roster") }} as t
            on e.student_number = t.student_number
            and s.expected_test_type = t.test_type
            and s.expected_score_type = t.score_type
            and s.expected_test_date = t.test_date
        where e.school_level = 'HS' and e.rn_year = 1
    ),

    base_rows_attempts_yearly as (
        select
            e.academic_year,
            e.student_number,
            e.studentid,
            e.students_dcid,
            e.salesforce_id,
            e.graduation_year,

            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_test_date,

            t.test_type,
            t.scope,
            t.score_type,

            count(concat(t.test_type, t.scope)) over (
                partition by
                    e.academic_year,
                    e.student_number,
                    s.expected_test_type,
                    s.expected_scope
                order by s.expected_test_date
            ) as test_count_yearly,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            strategy_attempts_ytd as s
            on e.academic_year = s.expected_test_academic_year
            and e.graduation_year = s.expected_graduation_year
        left join
            {{ ref("int_students__college_assessment_roster") }} as t
            on e.student_number = t.student_number
            and s.expected_test_type = t.test_type
            and s.expected_score_type = t.score_type
            and s.expected_test_date = t.test_date
        where e.school_level = 'HS' and e.rn_year = 1
    ),

    attempts_ytd as (
        select
            b.*,

            goal_category,

            g.min_score,
            g.pct_goal,

            concat(b.expected_scope, ' ', goal_category) as expected_metric_name,

            if(b.test_count_running >= g.min_score, 1, 0) as met_min_running,

        from base_rows_attempts_ytd as b
        cross join unnest(['Group 1', 'Group 2+']) as goal_category
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on b.expected_test_type = g.expected_test_type
            and b.expected_scope = g.expected_scope
            and b.expected_score_type = g.expected_score_type
            and goal_category = g.goal_category
    ),

    attempts_yearly as (
        select
            b.*,

            goal_category,

            g.min_score,
            g.pct_goal,

            concat(b.expected_scope, ' ', goal_category) as expected_metric_name,

            if(b.test_count_yearly >= g.min_score, 1, 0) as met_min_yearly,

        from base_rows_attempts_yearly as b
        cross join unnest(['Group 1', 'Group 2+']) as goal_category
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on b.expected_test_type = g.expected_test_type
            and b.expected_scope = g.expected_scope
            and b.expected_score_type = g.expected_score_type
            and goal_category = g.goal_category
    ),

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
            r1.student_number,

            s.expected_test_type,
            s.expected_score_type,
            s.expected_test_date,

            avg(r2.running_max_scale_score) as running_max_scale_score,
            avg(r2.running_superscore) as running_superscore,

        from {{ ref("int_students__college_assessment_roster") }} as r1
        inner join strategy as s on r1.graduation_year = s.expected_graduation_year
        left join
            {{ ref("int_students__college_assessment_roster") }} as r2
            on r1.student_number = r2.student_number
            and s.expected_test_type = r2.test_type
            and s.expected_score_type = r2.score_type
            and s.expected_test_date = r2.test_date
        group by
            r1.student_number,
            s.expected_test_type,
            s.expected_score_type,
            s.expected_test_date
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

            s.expected_test_academic_year,
            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_subject_area,
            s.expected_test_date,
            s.expected_test_month,
            s.expected_graduation_year,

            t.test_type,
            t.test_date,
            t.test_month,
            t.scope,
            t.subject_area,
            t.course_discipline,
            t.score_type,
            t.scale_score,
            t.previous_total_score_change,
            t.rn_highest,

            r2.max_scale_score,
            r2.superscore,

            r3.running_max_scale_score,
            r3.running_superscore,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            if(
                s.expected_subject_area in ('Composite', 'Combined'),
                'Total',
                s.expected_subject_area
            ) as expected_aligned_subject_area,

            avg(
                case
                    when bg.expected_metric_name in ('HS-Ready', 'College-Ready')
                    then t.scale_score
                    when bg.expected_metric_name like '%Group%'
                    then p1.met_min_yearly
                end
            ) as comparison_score,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    r3.running_max_scale_score,
                    p2.met_min_running
                )
            ) as running_max_comparison_score,

        from {{ ref("int_students__college_assessment_roster") }} as r1
        inner join
            strategy as s
            on r1.academic_year = s.expected_test_academic_year
            and r1.graduation_year = s.expected_graduation_year
        left join
            {{ ref("int_students__college_assessment_roster") }} as t
            on r1.student_number = t.student_number
            and s.expected_test_academic_year = t.academic_year
            and s.expected_score_type = t.score_type
            and s.expected_test_date = t.test_date
        left join
            max_scores as r2
            on r1.student_number = r2.student_number
            and s.expected_test_type = r2.expected_test_type
            and s.expected_score_type = r2.expected_score_type
        left join
            fill_scores as r3
            on r1.student_number = r3.student_number
            and s.expected_test_type = r3.expected_test_type
            and s.expected_score_type = r3.expected_score_type
            and s.expected_test_date = r3.expected_test_date
        left join
            benchmark_goals as bg
            on s.expected_test_type = bg.expected_test_type
            and s.expected_scope = bg.expected_scope
            and s.expected_score_type = bg.expected_score_type
        left join
            attempts_yearly as p1
            on r1.academic_year = p1.academic_year
            and r1.student_number = p1.student_number
            and s.expected_test_type = p1.expected_test_type
            and s.expected_scope = p1.scope
            and s.expected_score_type = p1.expected_score_type
            and s.expected_test_date = p1.expected_test_date
            and bg.expected_metric_name = p1.expected_metric_name
        left join
            attempts_ytd as p2
            on r1.student_number = p2.student_number
            and s.expected_test_type = p2.expected_test_type
            and s.expected_scope = p2.scope
            and s.expected_score_type = p2.expected_score_type
            and s.expected_test_date = p2.expected_test_date
            and bg.expected_metric_name = p2.expected_metric_name
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
            s.expected_test_academic_year,
            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_subject_area,
            s.expected_test_date,
            s.expected_test_month,
            s.expected_graduation_year,
            t.test_type,
            t.test_date,
            t.test_month,
            t.scope,
            t.subject_area,
            t.course_discipline,
            t.score_type,
            t.scale_score,
            t.previous_total_score_change,
            t.rn_highest,
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

    max(
        if(
            running_max_comparison_score >= expected_metric_min_score
            and expected_scope in ('ACT', 'SAT')
            and expected_subject_area in ('Composite', 'Combined', 'Reading', 'Math'),
            1,
            0
        )
    ) over (
        partition by
            student_number,
            expected_test_type,
            expected_aligned_subject_area,
            expected_metric_name
        order by grade_level
    ) as met_min_score_int_act_or_sat_overall_running,

    max(
        if(
            max_scale_score >= expected_metric_min_score
            and expected_scope in ('ACT', 'SAT')
            and expected_subject_area in ('Composite', 'Combined', 'Reading', 'Math'),
            1,
            0
        )
    ) over (
        partition by
            student_number,
            expected_test_type,
            expected_aligned_subject_area,
            expected_metric_name
    ) as met_min_score_int_act_or_sat_overall,

from roster
