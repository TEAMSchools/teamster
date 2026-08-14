with
    all_scores as (
        select
            student_number,
            administration_round,
            academic_year,
            test_date,
            test_month,
            test_type,
            scope,
            subject_area,
            aligned_subject_area,
            course_discipline,
            score_type,
            scale_score,
            rn_highest,
            aligned_subject,

            /* The administration a score belongs to, in the vocabulary the
               Expected Assessments tab uses. Official sittings are on College
               Board's national dates, so the month identifies the administration.
               Practice cannot use a month -- schools choose their own dates and one
               administration straddles two -- so it carries scope_round instead. */
            test_month as aligned_month_round,
            salesforce_id,
            is_overall_score,
            is_subject_score,
            n_overall_scores,
            n_subject_scores,
            strategy_case,
            surrogate_key,
            running_max_scale_score,
            max_scale_score,
            previous_total_score_change,
            superscore,
            avg_running_max_superscore,
            sum_running_max_superscore,
            runnning_superscore,

        from {{ ref("int_assessments__college_assessment") }}

        union all

        select
            powerschool_student_number as student_number,
            administration_round,
            academic_year,
            test_date,
            test_month,
            test_type,
            scope,
            subject_area,
            aligned_subject_area,
            course_discipline,
            score_type,
            scale_score,
            rn_highest,

            cast(null as string) as aligned_subject,

            scope_round as aligned_month_round,
            cast(null as string) as salesforce_id,

            is_overall_score,

            is_subject_score,

            cast(null as int64) as n_overall_scores,
            cast(null as int64) as n_subject_scores,

            strategy_case,

            cast(null as string) as surrogate_key,

            running_max_scale_score,
            max_scale_score,
            previous_total_score_change,

            cast(null as numeric) as superscore,
            cast(null as numeric) as avg_running_max_superscore,
            cast(null as numeric) as sum_running_max_superscore,
            cast(null as numeric) as runnning_superscore,

        from {{ ref("int_assessments__college_assessment_practice") }}
        where response_type != 'Group'
    ),

    benchmark_aligned as (
        select
            *,

            if(
                scope in ('PSAT10', 'PSAT NMSQT'), 'PSAT10/NMSQT', scope
            ) as benchmark_aligned_scope,

            scope != 'ACT'
            and score_type not in (
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            ) as is_benchmark_eligible,

            /* dense_rank on test_date, not row_number, because 261 official
               sittings carry the same score twice under different rn_highest.
               Its max is the distinct-date count, which count(*) would inflate. */
            dense_rank() over (
                partition by student_number, test_type, score_type order by test_date
            ) as rn_test_date,

            dense_rank() over (
                partition by academic_year, student_number, test_type, score_type
                order by test_date
            ) as rn_test_date_year,

        from all_scores
    ),

    /* One row per administration per score type, so the change below is measured
       between administrations rather than between duplicate rows. 261 official
       sittings carry the same score twice under different rn_highest, and lagging
       over those directly would read a change of zero between a row and its own
       duplicate. */
    admin_scores as (
        select
            student_number,
            test_type,
            score_type,
            test_date,

            max(scale_score) as admin_scale_score,

        from benchmark_aligned
        where test_date is not null and scale_score is not null
        group by student_number, test_type, score_type, test_date
    ),

    /* Change between consecutive administrations, for every score type rather than
       totals only, so a future view can report growth on sections as well.

       test_type is deliberately NOT in the partition. Every other partition in this
       lineage carries it, because a practice score must never displace an official
       one -- but growth is the exception: a student's progression runs through both,
       and chaining them is the point. Scores stay comparable because a practice
       score is converted onto the same scale as its official counterpart.

       Nothing reads this yet. It exists for the growth-over-time work due shortly
       after this PR. */
    admin_growth as (
        select
            student_number,
            test_type,
            score_type,
            test_date,

            admin_scale_score - lag(admin_scale_score) over (
                partition by student_number, score_type
                order by test_date asc, test_type asc
            ) as previous_score_change,

        from admin_scores
    )

select
    b.student_number,
    b.administration_round,
    b.academic_year,
    b.test_date,
    b.test_month,
    b.test_type,
    b.scope,
    b.benchmark_aligned_scope,
    b.subject_area,
    b.aligned_subject_area,
    b.aligned_subject,
    b.course_discipline,
    b.score_type,
    b.scale_score,
    b.rn_highest,
    b.aligned_month_round,
    b.salesforce_id,
    b.is_overall_score,
    b.is_subject_score,
    b.is_benchmark_eligible,
    b.n_overall_scores,
    b.n_subject_scores,
    b.strategy_case,
    b.surrogate_key,
    b.running_max_scale_score,
    b.max_scale_score,
    b.previous_total_score_change,
    b.superscore,
    b.avg_running_max_superscore,
    b.sum_running_max_superscore,
    b.runnning_superscore,

    g.previous_score_change,

    /* Total rows only. A subject score type's partition holds no total rows, so
       the guard lands null there rather than a section-score count. */
    if(
        b.is_overall_score = 1,
        max(b.rn_test_date) over (
            partition by b.student_number, b.test_type, b.score_type
        ),
        null
    ) as attempt_lifetime,

    if(
        b.is_overall_score = 1,
        max(b.rn_test_date_year) over (
            partition by b.academic_year, b.student_number, b.test_type, b.score_type
        ),
        null
    ) as yearly_attempts_totals,

    /* Tags the row a consumer filters on, replacing the dedupe
       rpt_tableau__college_assessment_dashboard_benchmark_calcs performs.
       subject_area rather than score_type so PSAT10 and NMSQT compete for the
       same subject; test_type so a practice score never outranks an official
       one; is_benchmark_eligible so ineligible rows never consume a rank. */
    if(
        b.is_benchmark_eligible,
        row_number() over (
            partition by
                b.student_number,
                b.test_type,
                b.benchmark_aligned_scope,
                b.subject_area,
                b.is_benchmark_eligible
            order by b.scale_score desc
        ),
        null
    ) as rn_highest_benchmark_aligned_scope,

    /* rn_highest = 1 is redundant to a max and suppresses 23 real scores. Kept
       to match production while the repointing is verified. See TODO(#4658). */
    max(if(b.is_benchmark_eligible and b.rn_highest = 1, b.scale_score, null)) over (
        partition by
            b.student_number, b.test_type, b.benchmark_aligned_scope, b.subject_area
    ) as benchmark_aligned_scope_max_score,

from benchmark_aligned as b
left join
    admin_growth as g
    on b.student_number = g.student_number
    and b.test_type = g.test_type
    and b.score_type = g.score_type
    and b.test_date = g.test_date
