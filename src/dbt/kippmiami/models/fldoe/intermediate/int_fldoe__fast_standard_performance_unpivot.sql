select
    student_id,
    academic_year,
    administration_window,
    assessment_grade,
    assessment_subject,

    performance,

    replace(`standard`, '_performance', '') as `standard`,

    case
        performance
        when 'Below the Standard'
        then 1
        when 'At/Near the Standard'
        then 2
        when 'Above the Standard'
        then 3
    end as performance_int,
from
    {{ ref("stg_fldoe__fast") }} unpivot (
        performance for `standard` in (
            reading_prose_and_poetry_performance,
            reading_informational_text_performance,
            reading_across_genres_vocabulary_performance,
            number_sense_and_additive_reasoning_performance,
            number_sense_and_operations_and_algebraic_reasoning_performance,
            number_sense_and_operations_and_probability_performance,
            number_sense_and_operations_performance,
            number_sense_and_operations_with_whole_numbers_performance,
            number_sense_and_multiplicative_reasoning_performance,
            number_sense_and_operations_with_fractions_and_decimals_performance,
            proportional_reasoning_and_relationships_performance,
            fractional_reasoning_performance,
            geometric_reasoning_data_analysis_and_probability_performance,
            linear_relationships_data_analysis_and_functions_performance,
            data_analysis_and_probability_performance,
            algebraic_reasoning_performance,
            geometric_reasoning_performance,
            -- trunk-ignore(sqlfluff/LT05)
            geometric_reasoning_measurement_and_data_analysis_and_probability_performance
        )
    )
