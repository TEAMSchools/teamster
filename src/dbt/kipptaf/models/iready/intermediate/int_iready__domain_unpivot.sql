with
    domain_unpivot as (
        select
            _dbt_source_relation,
            student_id,
            `subject`,
            illuminate_subject,
            academic_year_int,
            `start_date`,
            completion_date,
            test_round,
            _dbt_source_project,
            domain_name,
            placement,
            relative_placement,
            scale_score,
        from
            {{ ref("int_iready__diagnostic_results") }} unpivot (
                (placement, relative_placement, scale_score) for domain_name in (
                    (
                        phonics_placement,
                        phonics_relative_placement,
                        phonics_scale_score
                    ) as 'phonics',
                    (
                        algebra_and_algebraic_thinking_placement,
                        algebra_and_algebraic_thinking_relative_placement,
                        algebra_and_algebraic_thinking_scale_score
                    ) as 'algebra_and_algebraic_thinking',
                    (
                        geometry_placement,
                        geometry_relative_placement,
                        geometry_scale_score
                    ) as 'geometry',
                    (
                        measurement_and_data_placement,
                        measurement_and_data_relative_placement,
                        measurement_and_data_scale_score
                    ) as 'measurement_and_data',
                    (
                        number_and_operations_placement,
                        number_and_operations_relative_placement,
                        number_and_operations_scale_score
                    ) as 'number_and_operations',
                    (
                        high_frequency_words_placement,
                        high_frequency_words_relative_placement,
                        high_frequency_words_scale_score
                    ) as 'high_frequency_words',
                    (
                        phonological_awareness_placement,
                        phonological_awareness_relative_placement,
                        phonological_awareness_scale_score
                    ) as 'phonological_awareness',
                    (
                        reading_comprehension_informational_text_placement,
                        reading_comprehension_informational_text_relative_placement,
                        reading_comprehension_informational_text_scale_score
                    ) as 'reading_comprehension_informational_text',
                    (
                        reading_comprehension_literature_placement,
                        reading_comprehension_literature_relative_placement,
                        reading_comprehension_literature_scale_score
                    ) as 'reading_comprehension_literature',
                    (
                        reading_comprehension_overall_placement,
                        reading_comprehension_overall_relative_placement,
                        reading_comprehension_overall_scale_score
                    ) as 'reading_comprehension_overall',
                    (
                        vocabulary_placement,
                        vocabulary_relative_placement,
                        vocabulary_scale_score
                    ) as 'vocabulary',
                    (
                        comprehension_informational_text_placement,
                        comprehension_informational_text_relative_placement,
                        comprehension_informational_text_scale_score
                    ) as 'comprehension_informational_text',
                    (
                        comprehension_literature_placement,
                        comprehension_literature_relative_placement,
                        comprehension_literature_scale_score
                    ) as 'comprehension_literature',
                    (
                        comprehension_overall_placement,
                        comprehension_overall_relative_placement,
                        comprehension_overall_scale_score
                    ) as 'comprehension_overall'
                )
            )
        where relative_placement is not null
    )

select
    student_id,
    `subject`,
    illuminate_subject,
    academic_year_int,
    `start_date`,
    completion_date,
    test_round,
    _dbt_source_project,
    domain_name,
    placement,
    relative_placement,
    scale_score,

    row_number() over (
        partition by
            _dbt_source_relation,
            student_id,
            `subject`,
            academic_year_int,
            `start_date`,
            completion_date
        order by domain_name asc
    ) as rn_subject_test,
from domain_unpivot
