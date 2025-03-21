with
    domain_unpivot as (
        select
            _dbt_source_relation,
            student_id,
            `subject`,
            academic_year_int,
            `start_date`,
            completion_date,
            domain_name,
            relative_placement,
        from
            {{ ref("stg_iready__diagnostic_results") }} unpivot (
                relative_placement for domain_name in (
                    phonics_relative_placement,
                    algebra_and_algebraic_thinking_relative_placement,
                    geometry_relative_placement,
                    measurement_and_data_relative_placement,
                    number_and_operations_relative_placement,
                    high_frequency_words_relative_placement,
                    phonological_awareness_relative_placement,
                    reading_comprehension_informational_text_relative_placement,
                    reading_comprehension_literature_relative_placement,
                    reading_comprehension_overall_relative_placement,
                    vocabulary_relative_placement,
                    comprehension_informational_text_relative_placement,
                    comprehension_literature_relative_placement,
                    comprehension_overall_relative_placement
                )
            )
    )

select
    student_id,
    `subject`,
    academic_year_int,
    `start_date`,
    completion_date,
    domain_name,
    relative_placement,

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
