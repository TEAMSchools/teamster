with
    lessons_unpivot as (
        select
            student_id,
            academic_year_int,
            `subject`,
            date_range,
            date_range_start,
            date_range_end,

            /* unpivot cols */
            domain,
            completed,
            passed,
            percent_passed,
        from
            {{ ref("stg_iready__personalized_instruction_summary") }} unpivot (
                (completed, passed, percent_passed)
                for domain in (
                    /* math */
                    (
                        algebra_and_algebraic_thinking_lessons_completed,
                        algebra_and_algebraic_thinking_lessons_passed,
                        algebra_and_algebraic_thinking_percent_lessons_passed
                    ) as 'algebra_and_algebraic_thinking',
                    (
                        geometry_lessons_completed,
                        geometry_lessons_passed,
                        geometry_percent_lessons_passed
                    ) as 'geometry',
                    (
                        measurement_and_data_lessons_completed,
                        measurement_and_data_lessons_passed,
                        measurement_and_data_percent_lessons_passed
                    ) as 'measurement_and_data',
                    (
                        number_and_operations_lessons_completed,
                        number_and_operations_lessons_passed,
                        number_and_operations_percent_lessons_passed
                    ) as 'number_and_operations',
                    /* ela */
                    (
                        comprehension_close_reading_lessons_completed,
                        comprehension_close_reading_lessons_passed,
                        comprehension_close_reading_percent_lessons_passed
                    ) as 'comprehension_close_reading',
                    (
                        high_frequency_words_lessons_completed,
                        high_frequency_words_lessons_passed,
                        high_frequency_words_percent_lessons_passed
                    ) as 'high_frequency_words_standard',
                    (
                        phonics_lessons_completed,
                        phonics_lessons_passed,
                        phonics_percent_lessons_passed
                    ) as 'phonics',
                    (
                        phonological_awareness_lessons_completed,
                        phonological_awareness_lessons_passed,
                        phonological_awareness_percent_lessons_passed
                    ) as 'phonological_awareness',
                    (
                        language_structures_lessons_completed,
                        language_structures_lessons_passed,
                        language_structures_percent_lessons_passed
                    ) as 'language_structures',
                    (
                        comprehension_lessons_completed,
                        comprehension_lessons_passed,
                        comprehension_percent_lessons_passed
                    ) as 'comprehension',
                    (
                        vocabulary_lessons_completed,
                        vocabulary_lessons_passed,
                        vocabulary_percent_lessons_passed
                    ) as 'vocabulary',
                    /* math pro */
                    (
                        data_statistics_and_probability_skills_completed,
                        data_statistics_and_probability_skills_successful,
                        data_statistics_and_probability_percent_skills_successful
                    ) as 'data_statistics_and_probability',
                    (
                        decimals_and_operations_skills_completed,
                        decimals_and_operations_skills_successful,
                        decimals_and_operations_percent_skills_successful
                    ) as 'decimals_and_operations',
                    (
                        equations_and_functions_skills_completed,
                        equations_and_functions_skills_successful,
                        equations_and_functions_percent_skills_successful
                    ) as 'equations_and_functions',
                    (
                        fractions_and_operations_skills_completed,
                        fractions_and_operations_skills_successful,
                        fractions_and_operations_percent_skills_successful
                    ) as 'fractions_and_operations',
                    (
                        geometric_measurement_and_figures_skills_completed,
                        geometric_measurement_and_figures_skills_successful,
                        geometric_measurement_and_figures_percent_skills_successful
                    ) as 'geometric_measurement_and_figures',
                    (
                        rational_numbers_and_operations_skills_completed,
                        rational_numbers_and_operations_skills_successful,
                        rational_numbers_and_operations_percent_skills_successful
                    ) as 'rational_numbers_and_operations',
                    (
                        ratios_and_proportions_skills_completed,
                        ratios_and_proportions_skills_successful,
                        ratios_and_proportions_percent_skills_successful
                    ) as 'ratios_and_proportions',
                    (
                        whole_numbers_and_operations_skills_completed,
                        whole_numbers_and_operations_skills_successful,
                        whole_numbers_and_operations_percent_skills_successful
                    ) as 'whole_numbers_and_operations',
                    /* ela pro */
                    (
                        endings_affixes_skills_completed,
                        endings_affixes_skills_successful,
                        endings_affixes_percent_skills_successful
                    ) as 'endings_affixes',
                    (
                        high_frequency_words_skills_completed,
                        high_frequency_words_skills_successful,
                        high_frequency_words_percent_skills_successful
                    ) as 'high_frequency_words_pro',
                    (
                        multi_syllable_skills_completed,
                        multi_syllable_skills_successful,
                        multi_syllable_percent_skills_successful
                    ) as 'multi_syllable',
                    (
                        single_syllable_skills_completed,
                        single_syllable_skills_successful,
                        single_syllable_percent_skills_successful
                    ) as 'single_syllable'
                )
            )
    )

select
    student_id,
    academic_year_int,
    `subject`,
    date_range,
    date_range_start,
    date_range_end,
    completed,
    passed,
    percent_passed,

    if(
        domain like 'high_frequency_words_%', 'high_frequency_words', domain
    ) as `domain`,

    case
        when
            domain in (
                'algebra_and_algebraic_thinking',
                'comprehension_close_reading',
                'comprehension',
                'geometry',
                'high_frequency_words_standard',
                'language_structures',
                'measurement_and_data',
                'number_and_operations',
                'phonics',
                'phonological_awareness',
                'vocabulary'
            )
        then 'Standard'
        when
            domain in (
                'data_statistics_and_probability',
                'decimals_and_operations',
                'endings_affixes',
                'equations_and_functions',
                'fractions_and_operations',
                'geometric_measurement_and_figures',
                'high_frequency_words_pro',
                'multi_syllable',
                'rational_numbers_and_operations',
                'ratios_and_proportions',
                'single_syllable'
                'whole_numbers_and_operations'
            )
        then 'Pro'
    end as lesson_type,
from lessons_unpivot
