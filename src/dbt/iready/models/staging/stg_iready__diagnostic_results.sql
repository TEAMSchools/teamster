with
    hs_growth_data as (
        select
            'Mid or Above Grade Level' as fall_diagnostic_placement_level,
            'Math' as subject,
            9 as typical_growth_measure,
            19 as stretch_growth_measure,
        union all
        select
            'Early On Grade Level' as fall_diagnostic_placement_level,
            'Math' as `subject`,
            9 as typical_growth_measure,
            21 as stretch_growth_measure,
        union all
        select
            '1 Grade Level Below' as fall_diagnostic_placement_level,
            'Math' as `subject`,
            9 as typical_growth_measure,
            22 as stretch_growth_measure,
        union all
        select
            '2 Grade Levels Below' as fall_diagnostic_placement_level,
            'Math' as `subject`,
            10 as typical_growth_measure,
            23 as stretch_growth_measure,
        union all
        select
            '3 or More Grade Levels Below' as fall_diagnostic_placement_level,
            'Math' as `subject`,
            12 as typical_growth_measure,
            31 as stretch_growth_measure,
        union all
        select
            'Mid or Above Grade Level' as fall_diagnostic_placement_level,
            'Reading' as `subject`,
            4 as typical_growth_measure,
            13 as stretch_growth_measure,
        union all
        select
            'Early On Grade Level' as fall_diagnostic_placement_level,
            'Reading' as `subject`,
            4 as typical_growth_measure,
            22 as stretch_growth_measure,
        union all
        select
            '1 Grade Level Below' as fall_diagnostic_placement_level,
            'Reading' as `subject`,
            9 as typical_growth_measure,
            25 as stretch_growth_measure,
        union all
        select
            '2 Grade Levels Below' as fall_diagnostic_placement_level,
            'Reading' as `subject`,
            12 as typical_growth_measure,
            36 as stretch_growth_measure,
        union all
        select
            '3 or More Grade Levels Below' as fall_diagnostic_placement_level,
            'Reading' as `subject`,
            18 as typical_growth_measure,
            50 as stretch_growth_measure,
    ),

    hs_growth_measures as (
        select
            cast(grade_level as string) as grade_level,
            hs.fall_diagnostic_placement_level,
            hs.`subject`,
            hs.typical_growth_measure,
            hs.stretch_growth_measure,
        from hs_growth_data as hs
        cross join unnest([9, 10, 11, 12]) as grade_level
    ),

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

    calculations as (
        select
            t.* (
                except
                t.annual_typical_growth_measure,
                t.annual_stretch_growth_measure
            ),

            coalesce(
                t.annual_typical_growth_measure, hs.typical_growth_measure
            ) as annual_typical_growth_measure,
            coalesce(
                t.annual_stretch_growth_measure, hs.stretch_growth_measure
            ) as annual_stretch_growth_measure,

            coalesce(t.annual_typical_growth_measure, hs.typical_growth_measure)
            - t.diagnostic_gain as typical_growth,
            coalesce(t.annual_stretch_growth_measure, hs.stretch_growth_measure)
            - t.diagnostic_gain as stretch_growth,
        from transformations as t
        left join
            hs_growth_measures as hs
            on t.student_grade = hs.grade_level
            and t.`subject` = hs.`subject`
            and t.overall_relative_placement = hs.fall_diagnostic_placement_level
    )

select
    *,

    overall_scale_score + if(
        typical_growth > 0, typical_growth, 0
    ) as overall_scale_score_plus_typical_growth,

    overall_scale_score + if(
        stretch_growth > 0, stretch_growth, 0
    ) as overall_scale_score_plus_stretch_growth,

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
from calculations
