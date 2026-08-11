with
    practice as (
        select
            powerschool_student_number as student_number,
            administration_round,
            academic_year,
            test_date,
            test_month,
            subject_area,
            course_discipline,
            score_type,
            scale_score,

            'Practice' as test_type,

            /* NAMING TRAP: the practice hub's test_type holds the test itself and
               its scope holds Illuminate's Benchmark or null. Both are corrected
               here so the union speaks the official hub's vocabulary. */
            test_type as scope,

            if(
                subject_area in ('Composite', 'Combined'), 'Total', aligned_subject_area
            ) as aligned_subject_area,

            row_number() over (
                partition by powerschool_student_number, test_type, score_type
                order by scale_score desc
            ) as rn_highest,

        from {{ ref("int_assessments__college_assessment_practice") }}
    ),

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

            cast(null as string) as aligned_subject,
            cast(null as string) as salesforce_id,
            cast(null as int64) as is_overall_score,
            cast(null as int64) as is_subject_score,
            cast(null as int64) as n_overall_scores,
            cast(null as int64) as n_subject_scores,
            cast(null as string) as strategy_case,
            cast(null as string) as surrogate_key,
            cast(null as numeric) as running_max_scale_score,
            cast(null as numeric) as max_scale_score,
            cast(null as numeric) as previous_total_score_change,
            cast(null as numeric) as superscore,
            cast(null as numeric) as avg_running_max_superscore,
            cast(null as numeric) as sum_running_max_superscore,
            cast(null as numeric) as runnning_superscore,

        from practice
    ),

    benchmark_aligned as (
        select
            *,

            if(
                scope in ('PSAT10', 'PSAT NMSQT'), 'PSAT10/NMSQT', scope
            ) as benchmark_aligned_scope,

            /* coalesce keeps this false rather than null on practice composite
               rows, whose score_type is null. A null would drop them from the
               aligned maxes below. */
            scope != 'ACT'
            and coalesce(score_type, 'not a sub-test') not in (
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            ) as is_benchmark_eligible,

        from all_scores
    )

select
    student_number,
    administration_round,
    academic_year,
    test_date,
    test_month,
    test_type,
    scope,
    benchmark_aligned_scope,
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
        partition by student_number, test_type, benchmark_aligned_scope, subject_area
    ) as max_benchmark_aligned_scale_score_within_test_type,

    max(if(is_benchmark_eligible and rn_highest = 1, scale_score, null)) over (
        partition by student_number, benchmark_aligned_scope, subject_area
    ) as max_benchmark_aligned_scale_score_across_test_types,

from benchmark_aligned
