with
    strategy as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            academic_year as expected_test_academic_year,
            test_type as expected_test_type,
            test_date as expected_test_date,
            test_month as expected_test_month,
            scope as expected_scope,
            subject_area as expected_subject_area,
            aligned_subject_area as expected_aligned_subject_area,
            score_type as expected_score_type,
            graduation_year as expected_graduation_year,

        from {{ ref("int_students__college_assessment_roster") }}
    ),

    strategy_attempts_ytd as (
        -- need a distinct list of possible assessments throughout the years
        select distinct
            academic_year as expected_test_academic_year,
            test_type as expected_test_type,
            test_date as expected_test_date,
            test_month as expected_test_month,
            scope as expected_scope,
            subject_area as expected_subject_area,
            score_type as expected_score_type,
            aligned_subject_area as expected_aligned_subject_area,
            graduation_year as expected_graduation_year,

        from {{ ref("int_students__college_assessment_roster") }}
        where
            score_type in (
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

            g.min_score,
            g.pct_goal,
            g.expected_metric_name,

            if(b.test_count_running >= g.min_score, 1, 0) as met_min_running,

        from base_rows_attempts_ytd as b
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on b.expected_test_type = g.expected_test_type
            and b.expected_scope = g.expected_scope
            and b.expected_score_type = g.expected_score_type
            and g.expected_goal_type = 'Attempts'
    ),

    attempts_yearly as (
        select
            b.*,

            g.min_score,
            g.pct_goal,
            g.expected_metric_name,

            if(b.test_count_yearly >= g.min_score, 1, 0) as met_min_yearly,

        from base_rows_attempts_yearly as b
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as g
            on b.expected_test_type = g.expected_test_type
            and b.expected_scope = g.expected_scope
            and b.expected_score_type = g.expected_score_type
            and g.expected_goal_type = 'Attempts'
    ),

    max_scores as (
        select
            student_number,
            test_type as expected_test_type,
            score_type as expected_score_type,

            avg(max_scale_score) as max_scale_score,
            avg(superscore) as superscore,

        from {{ ref("int_students__college_assessment_roster") }}
        group by student_number, test_type, score_type
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
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.students_dcid,
            e.studentid,
            e.salesforce_id,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.student_email,
            e.enroll_status,
            e.iep_status,
            e.rn_undergrad,
            e.is_504,
            e.lep_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.gifted_and_talented,
            e.advisory,
            e.grad_iep_exempt_status_overall,
            e.contact_owner_name,
            e.cumulative_y1_gpa,
            e.cumulative_y1_gpa_projected,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            s.expected_test_academic_year,
            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_subject_area,
            s.expected_test_date,
            s.expected_test_month,
            s.expected_graduation_year,
            s.expected_aligned_subject_area,

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

            m.max_scale_score,
            m.superscore,

            f.running_max_scale_score,
            f.running_superscore,

            bg.expected_metric_name,
            bg.min_score as expected_metric_min_score,
            bg.pct_goal as expected_metric_pct_goal,

            avg(
                case
                    when bg.expected_metric_name in ('HS-Ready', 'College-Ready')
                    then t.scale_score
                    when bg.expected_metric_name like '%Attempt%'
                    then p1.met_min_yearly
                end
            ) as comparison_score,

            avg(
                if(
                    bg.expected_metric_name in ('HS-Ready', 'College-Ready'),
                    f.running_max_scale_score,
                    p2.met_min_running
                )
            ) as running_max_comparison_score,

            max(if(m.max_scale_score >= bg.min_score, 1, 0)) over (
                partition by
                    e.student_number,
                    s.expected_test_type,
                    s.expected_score_type,
                    bg.expected_metric_name
                order by s.expected_test_date
            ) as met_min_score_int_overall,

            max(
                if(
                    m.max_scale_score >= bg.min_score
                    and s.expected_scope in ('ACT', 'SAT')
                    and s.expected_subject_area
                    in ('Composite', 'Combined', 'Reading', 'Math', 'EBRW'),
                    1,
                    0
                )
            ) over (
                partition by
                    e.student_number,
                    s.expected_test_type,
                    s.expected_aligned_subject_area,
                    bg.expected_metric_name
            ) as met_min_score_int_act_or_sat_overall,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            strategy as s
            on e.academic_year = s.expected_test_academic_year
            and e.graduation_year = s.expected_graduation_year
        left join
            {{ ref("int_students__college_assessment_roster") }} as t
            on e.student_number = t.student_number
            and s.expected_test_academic_year = t.academic_year
            and s.expected_score_type = t.score_type
            and s.expected_test_date = t.test_date
        left join
            max_scores as m
            on e.student_number = m.student_number
            and s.expected_test_type = m.expected_test_type
            and s.expected_score_type = m.expected_score_type
        left join
            fill_scores as f
            on e.student_number = f.student_number
            and s.expected_test_type = f.expected_test_type
            and s.expected_score_type = f.expected_score_type
            and s.expected_test_date = f.expected_test_date
        left join
            {{ ref("stg_google_sheets__kippfwd_goals") }} as bg
            on s.expected_test_type = bg.expected_test_type
            and s.expected_scope = bg.expected_scope
            and s.expected_score_type = bg.expected_score_type
            and bg.expected_goal_type != 'Board'
        left join
            attempts_yearly as p1
            on e.academic_year = p1.academic_year
            and e.student_number = p1.student_number
            and s.expected_test_type = p1.expected_test_type
            and s.expected_scope = p1.scope
            and s.expected_score_type = p1.expected_score_type
            and s.expected_test_date = p1.expected_test_date
            and bg.expected_metric_name = p1.expected_metric_name
        left join
            attempts_ytd as p2
            on e.student_number = p2.student_number
            and s.expected_test_type = p2.expected_test_type
            and s.expected_scope = p2.scope
            and s.expected_score_type = p2.expected_score_type
            and s.expected_test_date = p2.expected_test_date
            and bg.expected_metric_name = p2.expected_metric_name
        where e.school_level = 'HS' and e.rn_year = 1
        group by
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.region,
            e.schoolid,
            e.school,
            e.student_number,
            e.students_dcid,
            e.studentid,
            e.salesforce_id,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.student_email,
            e.enroll_status,
            e.iep_status,
            e.rn_undergrad,
            e.is_504,
            e.lep_status,
            e.ktc_cohort,
            e.graduation_year,
            e.year_in_network,
            e.gifted_and_talented,
            e.advisory,
            e.grad_iep_exempt_status_overall,
            e.contact_owner_name,
            e.cumulative_y1_gpa,
            e.cumulative_y1_gpa_projected,
            e.college_match_gpa,
            e.college_match_gpa_bands,
            s.expected_test_academic_year,
            s.expected_test_type,
            s.expected_scope,
            s.expected_score_type,
            s.expected_subject_area,
            s.expected_test_date,
            s.expected_test_month,
            s.expected_graduation_year,
            s.expected_aligned_subject_area,
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
            m.max_scale_score,
            m.superscore,
            f.running_max_scale_score,
            f.running_superscore,
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

    max(
        if(
            running_max_comparison_score >= expected_metric_min_score
            and expected_scope in ('ACT', 'SAT')
            and expected_subject_area
            in ('Composite', 'Combined', 'Reading', 'Math', 'EBRW'),
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

from roster
