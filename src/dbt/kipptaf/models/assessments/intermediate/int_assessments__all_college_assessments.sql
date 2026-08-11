with
    aligned as (
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
            aligned_subject,
            course_discipline,
            score_type,
            scale_score,
            rn_highest,
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

            if(
                scope in ('PSAT10', 'PSAT NMSQT'), 'PSAT10/NMSQT', scope
            ) as aligned_scope,

            scope != 'ACT'
            and score_type not in (
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            ) as is_benchmark_eligible,

        from {{ ref("int_assessments__college_assessment") }}
    )

select
    student_number,
    administration_round,
    academic_year,
    test_date,
    test_month,
    test_type,
    scope,
    aligned_scope,
    subject_area,
    aligned_subject_area,
    aligned_subject,
    course_discipline,
    score_type,
    scale_score,
    rn_highest,
    salesforce_id,
    is_overall_score,
    is_subject_score,
    is_benchmark_eligible,
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

    /* rn_highest = 1 is redundant to a max and suppresses 23 real scores. Kept
       to match production while the repointing is verified. See TODO(#4658). */
    max(if(is_benchmark_eligible and rn_highest = 1, scale_score, null)) over (
        partition by student_number, test_type, aligned_scope, subject_area
    ) as max_aligned_scale_score_within_test_type,

    max(if(is_benchmark_eligible and rn_highest = 1, scale_score, null)) over (
        partition by student_number, aligned_scope, subject_area
    ) as max_aligned_scale_score_across_test_types,

from aligned
