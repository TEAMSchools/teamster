with
    psat as (
        select
            local_student_id,
            academic_year,
            test_name,
            test_date,
            score,

            concat('psat_', score_type) as score_type,
        from
            {{ ref("stg_illuminate__psat") }} unpivot (
                score for score_type in (
                    advanced_math_subscore,
                    command_evidence_subscore,
                    eb_read_write_section_score,
                    english_conv_subscore,
                    expression_ideas_subscore,
                    heart_algebra_subscore,
                    history_cross_test_score,
                    math_test_score,
                    math_section_score,
                    prob_solve_data_subscore,
                    reading_test_score,
                    science_cross_test_score,
                    total_score,
                    relevant_words_subscore,
                    writing_test_score
                )
            )
    )

select
    *,

    row_number() over (
        partition by local_student_id, test_name, score_type order by score desc
    ) as rn_highest,
from psat
