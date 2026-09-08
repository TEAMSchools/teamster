with
    goals as (
        select
            test_type as expected_test_type,
            score_type as expected_score_type,
            expected_scope,
            expected_subject_area,
            expected_aligned_subject_area,
            expected_goal_type,
            expected_goal_subtype,
            expected_metric_name,
            expected_metric_label,
            expected_metric_goal as expected_metric_pct_goal,

            cast(grade_level as int64) as expected_grade_level,
            cast(expected_min_score as float64) as expected_metric_min_score,

        from {{ ref("int_google_sheets__kippfwd__goals_unpivot") }}
        where goal_branch = 'By Grade' and expected_scope != 'ACT'
    ),

    scores as (
        select
            student_number,
            test_type,
            scope,
            score_type,
            subject_area,

            -- float64 here so score stays float64 through the if() and the avg()
            cast(max(scale_score) as float64) as max_scale_score,

            max(attempt_lifetime) as attempt_count_lifetime,

        from {{ ref("int_assessments__all_college_assessments") }}
        group by student_number, test_type, scope, score_type, subject_area
    ),

    /* One row per student who holds any result at all, carrying a literal zero.
       An attempts metric reads that zero where the student never sat the test,
       and null where they hold no result of that test type at all -- which is
       what keeps the attempts denominator to test takers rather than to every
       enrolled student. Production got the same population by reading the
       participation roster, whose grain is enrollment intersected with results. */
    scored_students as (
        select student_number, test_type, 0 as zero_attempts,

        from {{ ref("int_assessments__all_college_assessments") }}
        group by student_number, test_type
    ),

    roster as (
        select
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.district,
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
            e.college_match_gpa,
            e.college_match_gpa_bands,

            g.expected_test_type,
            g.expected_scope,
            g.expected_subject_area,
            g.expected_aligned_subject_area,
            g.expected_score_type,
            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.expected_metric_label,
            g.expected_metric_min_score,
            g.expected_metric_pct_goal,

            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type,

            avg(
                if(
                    g.expected_goal_type = 'Attempts',
                    coalesce(s.attempt_count_lifetime, ss.zero_attempts),
                    s.max_scale_score
                )
            ) as score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        /* Only a total-level Benchmark is grade-specific, and it is reported only
           where a goal was set for that grade. Attempts apply to every student
           regardless of grade -- a grade 9 student has taken the SAT zero times,
           which is a reportable answer. Section thresholds likewise apply to
           everyone, which is how the retired sheet carried them, at no grade. */
        inner join
            goals as g
            on (
                g.expected_goal_type = 'Attempts'
                or g.expected_aligned_subject_area != 'Total'
                or e.grade_level = g.expected_grade_level
            )
        left join
            scores as s
            on e.student_number = s.student_number
            and g.expected_test_type = s.test_type
            and g.expected_score_type = s.score_type
        left join
            scored_students as ss
            on e.student_number = ss.student_number
            and g.expected_test_type = ss.test_type
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
            and not e.is_out_of_district
        group by
            e.academic_year,
            e.academic_year_display,
            e.state,
            e.district,
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
            e.college_match_gpa,
            e.college_match_gpa_bands,
            g.expected_test_type,
            g.expected_scope,
            g.expected_subject_area,
            g.expected_aligned_subject_area,
            g.expected_score_type,
            g.expected_goal_type,
            g.expected_goal_subtype,
            g.expected_metric_name,
            g.expected_metric_label,
            g.expected_metric_min_score,
            g.expected_metric_pct_goal,
            s.test_type,
            s.scope,
            s.subject_area,
            s.score_type
    ),

    tiers as (
        select
            *,

            if(score >= expected_metric_min_score, 1, 0) as met_min_score_int,

            if(
                (
                    expected_goal_subtype = '1 Attempt'
                    and score = expected_metric_min_score
                )
                or (
                    expected_goal_subtype != '1 Attempt'
                    and score >= expected_metric_min_score
                ),
                1,
                0
            ) as alt_met_min_score_int,

            /* Both tiers evaluated for the same student and score type, so the
               three-way bucket below can be read off one row. expected_test_type
               is in the partition because Official and Practice share one
               score_type vocabulary -- without it a practice score raises the
               official row's band, and vice versa. */
            max(
                if(
                    expected_goal_subtype = 'College-Ready'
                    and score >= expected_metric_min_score,
                    1,
                    0
                )
            ) over (
                partition by student_number, expected_test_type, expected_score_type
            ) as met_college_ready,

            max(
                if(
                    expected_goal_subtype = 'HS Grad-Ready'
                    and score >= expected_metric_min_score,
                    1,
                    0
                )
            ) over (
                partition by student_number, expected_test_type, expected_score_type
            ) as met_hs_ready,

        from roster
    )

select
    * except (met_college_ready, met_hs_ready),

    case
        when expected_goal_type != 'Benchmark' or score is null
        then null
        when met_college_ready = 1
        then 'College-Ready'
        when met_hs_ready = 1
        then 'HS Grad-Ready'
        else 'No Benchmark Met'
    end as benchmark_tier,

from tiers
