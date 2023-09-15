select
    student_id,
    academic_year,
    administration_window,
    assessment_grade,
    assessment_subject,

    standard,
    performance,
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
        performance for standard in (
            reading_prose_and_poetry,
            reading_informational_text,
            reading_across_genres_vocabulary,
            number_sense_and_additive_reasoning,
            number_sense_and_operations_and_algebraic_reasoning,
            number_sense_and_operations_and_probability,
            number_sense_and_operations,
            number_sense_and_operations_with_whole_numbers,
            number_sense_and_multiplicative_reasoning,
            number_sense_and_operations_with_fractions_and_decimals,
            proportional_reasoning_and_relationships,
            fractional_reasoning,
            geometric_reasoning_data_analysis_and_probability,
            linear_relationships_data_analysis_and_functions,
            data_analysis_and_probability,
            algebraic_reasoning,
            geometric_reasoning,
            geometric_reasoning_measurement_and_data_analysis_and_probability
        )
    )
