with
    diagnostic_results as (
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

            safe_cast(student_id as int) as student_id,

            parse_date('%m/%d/%Y', `start_date`) as `start_date`,
            parse_date('%m/%d/%Y', completion_date) as completion_date,
        from {{ source("iready", "src_iready__diagnostic_results") }}
    ),

    hs_goals as (
        select
            * except (annual_typical_growth_measure, annual_stretch_growth_measure),

            if(
                most_recent_diagnostic_ytd_y_n = 'Y', overall_scale_score, null
            ) as most_recent_overall_scale_score,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', overall_relative_placement, null
            ) as most_recent_overall_relative_placement,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', overall_placement, null
            ) as most_recent_overall_placement,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', diagnostic_gain, null
            ) as most_recent_diagnostic_gain,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', lexile_measure, null
            ) as most_recent_lexile_measure,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', lexile_range, null
            ) as most_recent_lexile_range,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', rush_flag, null
            ) as most_recent_rush_flag,
            if(
                most_recent_diagnostic_ytd_y_n = 'Y', completion_date, null
            ) as most_recent_completion_date,

            if(
                percent_progress_to_annual_typical_growth_percent >= 100, true, false
            ) as is_met_typical,
            if(
                percent_progress_to_annual_stretch_growth_percent >= 100, true, false
            ) as is_met_stretch,

            if(student_grade = 'K', 0, cast(student_grade as int)) as student_grade_int,

            case
                _dagster_partition_subject when 'ela' then 'ELA' when 'math' then 'Math'
            end as discipline,

            case
                _dagster_partition_subject
                when 'ela'
                then 'Reading'
                when 'math'
                then 'Math'
            end as `subject`,

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

            case
                when student_grade not in ('9', '10', '11', '12')
                then annual_typical_growth_measure
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = 'Mid or Above Grade Level'
                then 9
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = 'Early On Grade Level'
                then 9
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '1 Grade Level Below'
                then 9
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '2 Grade Levels Below'
                then 10
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '3 or More Grade Levels Below'
                then 12
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = 'Mid or Above Grade Level'
                then 4
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = 'Early On Grade Level'
                then 4
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '1 Grade Level Below'
                then 9
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '2 Grade Levels Below'
                then 12
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '3 or More Grade Levels Below'
                then 18
            end as annual_typical_growth_measure,

            case
                when student_grade not in ('9', '10', '11', '12')
                then annual_stretch_growth_measure
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = 'Mid or Above Grade Level'
                then 12
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = 'Early On Grade Level'
                then 21
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '1 Grade Level Below'
                then 22
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '2 Grade Levels Below'
                then 23
                when
                    _dagster_partition_subject = 'math'
                    and overall_relative_placement = '3 or More Grade Levels Below'
                then 31
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = 'Mid or Above Grade Level'
                then 13
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = 'Early On Grade Level'
                then 22
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '1 Grade Level Below'
                then 25
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '2 Grade Levels Below'
                then 36
                when
                    _dagster_partition_subject = 'ela'
                    and overall_relative_placement = '3 or More Grade Levels Below'
                then 50
            end as annual_stretch_growth_measure,
        from diagnostic_results
    ),

    growth_measures as (
        select
            *,

            annual_typical_growth_measure - diagnostic_gain as typical_growth,
            annual_stretch_growth_measure - diagnostic_gain as stretch_growth,

            if(overall_relative_placement_int >= 4, true, false) as is_proficient,
        from hs_goals
    ),

    calcs as (
        select
            * except (typical_growth, stretch_growth),

            if(typical_growth > 0, typical_growth, 0) as typical_growth,
            if(stretch_growth > 0, stretch_growth, 0) as stretch_growth,
        from growth_measures
    )

select
    *,

    overall_scale_score + typical_growth as overall_scale_score_plus_typical_growth,
    overall_scale_score + stretch_growth as overall_scale_score_plus_stretch_growth,
from calcs
