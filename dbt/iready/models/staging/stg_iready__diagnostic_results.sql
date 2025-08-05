with
    transformations as (
        select
            * except (
                `grouping`,
                `start_date`,
                `subject`,
                algebra_and_algebraic_thinking_scale_score,
                annual_stretch_growth_measure,
                annual_typical_growth_measure,
                completion_date,
                comprehension_informational_text_scale_score,
                comprehension_literature_scale_score,
                comprehension_overall_scale_score,
                diagnostic_gain,
                duration_min,
                geometry_scale_score,
                high_frequency_words_scale_score,
                measurement_and_data_scale_score,
                mid_on_grade_level_scale_score,
                most_recent_diagnostic_y_n,
                most_recent_diagnostic_ytd_y_n,
                number_and_operations_scale_score,
                overall_scale_score,
                percent_progress_to_annual_stretch_growth_percent,
                percent_progress_to_annual_typical_growth_percent,
                percentile,
                phonics_scale_score,
                phonological_awareness_scale_score,
                reading_comprehension_informational_text_scale_score,
                reading_comprehension_literature_scale_score,
                reading_comprehension_overall_scale_score,
                student_id,
                vocabulary_scale_score
            ),

            _dagster_partition_academic_year as academic_year_int,

            cast(overall_scale_score as int) as overall_scale_score,
            cast(duration_min as int) as duration_min,
            cast(student_id as int) as student_id,

            cast(
                percent_progress_to_annual_stretch_growth_percent as numeric
            ) as percent_progress_to_annual_stretch_growth_percent,
            cast(
                percent_progress_to_annual_typical_growth_percent as numeric
            ) as percent_progress_to_annual_typical_growth_percent,

            cast(cast(diagnostic_gain as numeric) as int) as diagnostic_gain,
            cast(
                cast(annual_stretch_growth_measure as numeric) as int
            ) as annual_stretch_growth_measure,
            cast(
                cast(annual_typical_growth_measure as numeric) as int
            ) as annual_typical_growth_measure,
            cast(cast(`grouping` as numeric) as int) as _grouping,
            cast(cast(percentile as numeric) as int) as percentile,
            cast(
                cast(algebra_and_algebraic_thinking_scale_score as numeric) as int
            ) as algebra_and_algebraic_thinking_scale_score,
            cast(
                cast(comprehension_informational_text_scale_score as numeric) as int
            ) as comprehension_informational_text_scale_score,
            cast(
                cast(comprehension_literature_scale_score as numeric) as int
            ) as comprehension_literature_scale_score,
            cast(
                cast(comprehension_overall_scale_score as numeric) as int
            ) as comprehension_overall_scale_score,
            cast(cast(geometry_scale_score as numeric) as int) as geometry_scale_score,
            cast(
                cast(high_frequency_words_scale_score as numeric) as int
            ) as high_frequency_words_scale_score,
            cast(
                cast(measurement_and_data_scale_score as numeric) as int
            ) as measurement_and_data_scale_score,
            cast(
                cast(mid_on_grade_level_scale_score as numeric) as int
            ) as mid_on_grade_level_scale_score,
            cast(
                cast(number_and_operations_scale_score as numeric) as int
            ) as number_and_operations_scale_score,
            cast(cast(phonics_scale_score as numeric) as int) as phonics_scale_score,
            cast(
                cast(phonological_awareness_scale_score as numeric) as int
            ) as phonological_awareness_scale_score,
            cast(
                cast(
                    reading_comprehension_informational_text_scale_score as numeric
                ) as int
            ) as reading_comprehension_informational_text_scale_score,
            cast(
                cast(reading_comprehension_literature_scale_score as numeric) as int
            ) as reading_comprehension_literature_scale_score,
            cast(
                cast(reading_comprehension_overall_scale_score as numeric) as int
            ) as reading_comprehension_overall_scale_score,
            cast(
                cast(vocabulary_scale_score as numeric) as int
            ) as vocabulary_scale_score,

            coalesce(
                most_recent_diagnostic_y_n, most_recent_diagnostic_ytd_y_n
            ) as most_recent_diagnostic_ytd_y_n,

            parse_date('%m/%d/%Y', `start_date`) as `start_date`,
            parse_date('%m/%d/%Y', completion_date) as completion_date,

            if(
                _dagster_partition_subject = 'ela',
                'Reading',
                initcap(_dagster_partition_subject)
            ) as `subject`,

            case
                overall_relative_placement
                when '3 or More Grade Levels Below'
                then 1
                when '2 Grade Levels Below'
                then 2
                when '1 Grade Level Below'
                then 3
                when 'Early On Grade Level'
                then 4
                when 'Mid or Above Grade Level'
                then 5
            end as overall_relative_placement_int,

            case
                when
                    overall_relative_placement
                    in ('Early On Grade Level', 'Mid or Above Grade Level')
                then 'On or Above Grade Level'
                when overall_relative_placement = '1 Grade Level Below'
                then overall_relative_placement
                when
                    overall_relative_placement
                    in ('2 Grade Levels Below', '3 or More Grade Levels Below')
                then 'Two or More Grade Levels Below'
            end as placement_3_level,
        from {{ source("iready", "src_iready__diagnostic_results") }}
    ),

    calculations as (
        select
            *,

            annual_typical_growth_measure - diagnostic_gain as typical_growth,
            annual_stretch_growth_measure - diagnostic_gain as stretch_growth,
        from transformations
    )

select
    *,

    overall_scale_score + if(
        typical_growth > 0, typical_growth, 0
    ) as overall_scale_score_plus_typical_growth,

    overall_scale_score + if(
        stretch_growth > 0, stretch_growth, 0
    ) as overall_scale_score_plus_stretch_growth,
from calculations
