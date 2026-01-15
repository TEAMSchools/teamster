with
    psat as (
        select local_student_id, academic_year, test_name, test_date, score, score_type,
        from
            {{ ref("stg_illuminate__national_assessments__psat") }} unpivot (
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
    * except (score_type),

    concat('psat_', score_type) as score_type,

    case
        when score_type in ('eb_read_write_section_score', 'reading_test_score')
        then 'ELA'
        when score_type in ('math_test_score', 'math_section_score')
        then 'Math'
    end as discipline,

    case
        score_type
        when 'total_score'
        then 'Composite'
        when 'reading_test_score'
        then 'Reading'
        when 'math_test_score'
        then 'Math Test'
        when 'math_section_score'
        then 'Math'
        when 'eb_read_write_section_score'
        then 'Writing and Language Test'
    end as subject_area,

    row_number() over (
        partition by local_student_id, test_name, score_type order by score desc
    ) as rn_highest,
from psat
