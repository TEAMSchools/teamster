select
    _dagster_partition_subject,
    academic_year,
    class_es,
    class_teacher_s,
    date_range,
    economically_disadvantaged,
    english_language_learner,
    enrolled,
    first_name,
    hispanic_or_latino,
    last_name,
    migrant,
    race,
    report_group_s,
    school,
    sex,
    special_education,
    student_grade,
    `subject`,
    user_name,

    cast(_dagster_partition_academic_year as int) as academic_year_int,
    cast(all_lessons_completed as int) as all_lessons_completed,
    cast(all_lessons_passed as int) as all_lessons_passed,
    cast(percent_all_lessons_passed as int) as percent_all_lessons_passed,
    cast(total_lesson_time_on_task_min as int) as total_lesson_time_on_task_min,

    /* math */
    cast(
        i_ready_algebra_and_algebraic_thinking_lessons_completed as int
    ) as algebra_and_algebraic_thinking_lessons_completed,
    cast(
        i_ready_algebra_and_algebraic_thinking_lessons_passed as int
    ) as algebra_and_algebraic_thinking_lessons_passed,
    cast(
        i_ready_algebra_and_algebraic_thinking_percent_lessons_passed as int
    ) as algebra_and_algebraic_thinking_percent_lessons_passed,
    cast(i_ready_geometry_lessons_completed as int) as geometry_lessons_completed,
    cast(i_ready_geometry_lessons_passed as int) as geometry_lessons_passed,
    cast(
        i_ready_geometry_percent_lessons_passed as int
    ) as geometry_percent_lessons_passed,
    cast(
        i_ready_measurement_and_data_lessons_completed as int
    ) as measurement_and_data_lessons_completed,
    cast(
        i_ready_measurement_and_data_lessons_passed as int
    ) as measurement_and_data_lessons_passed,
    cast(
        i_ready_measurement_and_data_percent_lessons_passed as int
    ) as measurement_and_data_percent_lessons_passed,
    cast(
        i_ready_number_and_operations_lessons_completed as int
    ) as number_and_operations_lessons_completed,
    cast(
        i_ready_number_and_operations_lessons_passed as int
    ) as number_and_operations_lessons_passed,
    cast(
        i_ready_number_and_operations_percent_lessons_passed as int
    ) as number_and_operations_percent_lessons_passed,
    cast(
        i_ready_pro_data_statistics_and_probability_percent_skills_successful as int
    ) as data_statistics_and_probability_percent_skills_successful,
    cast(
        i_ready_pro_data_statistics_and_probability_skills_completed as int
    ) as data_statistics_and_probability_skills_completed,
    cast(
        i_ready_pro_data_statistics_and_probability_skills_successful as int
    ) as data_statistics_and_probability_skills_successful,
    cast(
        i_ready_pro_decimals_and_operations_percent_skills_successful as int
    ) as decimals_and_operations_percent_skills_successful,
    cast(
        i_ready_pro_decimals_and_operations_skills_completed as int
    ) as decimals_and_operations_skills_completed,
    cast(
        i_ready_pro_decimals_and_operations_skills_successful as int
    ) as decimals_and_operations_skills_successful,
    cast(
        i_ready_pro_equations_and_functions_percent_skills_successful as int
    ) as equations_and_functions_percent_skills_successful,
    cast(
        i_ready_pro_equations_and_functions_skills_completed as int
    ) as equations_and_functions_skills_completed,
    cast(
        i_ready_pro_equations_and_functions_skills_successful as int
    ) as equations_and_functions_skills_successful,
    cast(
        i_ready_pro_fractions_and_operations_percent_skills_successful as int
    ) as fractions_and_operations_percent_skills_successful,
    cast(
        i_ready_pro_fractions_and_operations_skills_completed as int
    ) as fractions_and_operations_skills_completed,
    cast(
        i_ready_pro_fractions_and_operations_skills_successful as int
    ) as fractions_and_operations_skills_successful,
    cast(
        i_ready_pro_geometric_measurement_and_figures_percent_skills_successful as int
    ) as geometric_measurement_and_figures_percent_skills_successful,
    cast(
        i_ready_pro_geometric_measurement_and_figures_skills_completed as int
    ) as geometric_measurement_and_figures_skills_completed,
    cast(
        i_ready_pro_geometric_measurement_and_figures_skills_successful as int
    ) as geometric_measurement_and_figures_skills_successful,
    cast(
        i_ready_pro_rational_numbers_and_operations_percent_skills_successful as int
    ) as rational_numbers_and_operations_percent_skills_successful,
    cast(
        i_ready_pro_rational_numbers_and_operations_skills_completed as int
    ) as rational_numbers_and_operations_skills_completed,
    cast(
        i_ready_pro_rational_numbers_and_operations_skills_successful as int
    ) as rational_numbers_and_operations_skills_successful,
    cast(
        i_ready_pro_ratios_and_proportions_percent_skills_successful as int
    ) as ratios_and_proportions_percent_skills_successful,
    cast(
        i_ready_pro_ratios_and_proportions_skills_completed as int
    ) as ratios_and_proportions_skills_completed,
    cast(
        i_ready_pro_ratios_and_proportions_skills_successful as int
    ) as ratios_and_proportions_skills_successful,
    cast(
        i_ready_pro_whole_numbers_and_operations_percent_skills_successful as int
    ) as whole_numbers_and_operations_percent_skills_successful,
    cast(
        i_ready_pro_whole_numbers_and_operations_skills_completed as int
    ) as whole_numbers_and_operations_skills_completed,
    cast(
        i_ready_pro_whole_numbers_and_operations_skills_successful as int
    ) as whole_numbers_and_operations_skills_successful,

    /* ela */
    cast(
        i_ready_comprehension_close_reading_lessons_completed as int
    ) as comprehension_close_reading_lessons_completed,
    cast(
        i_ready_comprehension_close_reading_lessons_passed as int
    ) as comprehension_close_reading_lessons_passed,
    cast(
        i_ready_comprehension_close_reading_percent_lessons_passed as int
    ) as comprehension_close_reading_percent_lessons_passed,
    cast(
        i_ready_high_frequency_words_lessons_completed as int
    ) as high_frequency_words_lessons_completed,
    cast(
        i_ready_high_frequency_words_lessons_passed as int
    ) as high_frequency_words_lessons_passed,
    cast(
        i_ready_high_frequency_words_percent_lessons_passed as int
    ) as high_frequency_words_percent_lessons_passed,
    cast(i_ready_phonics_lessons_completed as int) as phonics_lessons_completed,
    cast(i_ready_phonics_lessons_passed as int) as phonics_lessons_passed,
    cast(
        i_ready_phonics_percent_lessons_passed as int
    ) as phonics_percent_lessons_passed,
    cast(
        i_ready_phonological_awareness_lessons_completed as int
    ) as phonological_awareness_lessons_completed,
    cast(
        i_ready_phonological_awareness_lessons_passed as int
    ) as phonological_awareness_lessons_passed,
    cast(
        i_ready_phonological_awareness_percent_lessons_passed as int
    ) as phonological_awareness_percent_lessons_passed,
    cast(
        i_ready_pro_endings_affixes_percent_skills_successful as int
    ) as endings_affixes_percent_skills_successful,
    cast(
        i_ready_pro_endings_affixes_skills_completed as int
    ) as endings_affixes_skills_completed,
    cast(
        i_ready_pro_endings_affixes_skills_successful as int
    ) as endings_affixes_skills_successful,
    cast(
        i_ready_pro_high_frequency_words_percent_skills_successful as int
    ) as high_frequency_words_percent_skills_successful,
    cast(
        i_ready_pro_high_frequency_words_skills_completed as int
    ) as high_frequency_words_skills_completed,
    cast(
        i_ready_pro_high_frequency_words_skills_successful as int
    ) as high_frequency_words_skills_successful,
    cast(
        i_ready_pro_language_structures_lessons_completed as int
    ) as language_structures_lessons_completed,
    cast(
        i_ready_pro_language_structures_lessons_passed as int
    ) as language_structures_lessons_passed,
    cast(
        i_ready_pro_language_structures_percent_lessons_passed as int
    ) as language_structures_percent_lessons_passed,
    cast(
        i_ready_pro_multi_syllable_percent_skills_successful as int
    ) as multi_syllable_percent_skills_successful,
    cast(
        i_ready_pro_multi_syllable_skills_completed as int
    ) as multi_syllable_skills_completed,
    cast(
        i_ready_pro_multi_syllable_skills_successful as int
    ) as multi_syllable_skills_successful,
    cast(
        i_ready_pro_single_syllable_percent_skills_successful as int
    ) as single_syllable_percent_skills_successful,
    cast(
        i_ready_pro_single_syllable_skills_completed as int
    ) as single_syllable_skills_completed,
    cast(
        i_ready_pro_single_syllable_skills_successful as int
    ) as single_syllable_skills_successful,

    coalesce(
        cast(i_ready_comprehension_lessons_completed as int),
        cast(i_ready_pro_comprehension_lessons_completed as int)
    ) as comprehension_lessons_completed,

    coalesce(
        cast(i_ready_comprehension_lessons_passed as int),
        cast(i_ready_pro_comprehension_lessons_passed as int)
    ) as comprehension_lessons_passed,

    coalesce(
        cast(i_ready_comprehension_percent_lessons_passed as int),
        cast(i_ready_pro_comprehension_percent_lessons_passed as int)
    ) as comprehension_percent_lessons_passed,
    coalesce(
        cast(i_ready_vocabulary_lessons_completed as int),
        cast(i_ready_pro_vocabulary_lessons_completed as int)
    ) as vocabulary_lessons_completed,

    coalesce(
        cast(i_ready_vocabulary_lessons_passed as int),
        cast(i_ready_pro_vocabulary_lessons_passed as int)
    ) as vocabulary_lessons_passed,

    coalesce(
        cast(i_ready_vocabulary_percent_lessons_passed as int),
        cast(i_ready_pro_vocabulary_percent_lessons_passed as int)
    ) as vocabulary_percent_lessons_passed,

    safe_cast(student_id as int) as student_id,

    parse_date('%m/%d/%Y', date_range_start) as date_range_start,
    parse_date('%m/%d/%Y', date_range_end) as date_range_end,
from {{ source("iready", "src_iready__personalized_instruction_summary") }}
