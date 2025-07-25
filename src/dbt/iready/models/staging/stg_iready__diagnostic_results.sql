with
    transformations as (
        select
            * except (
                annual_stretch_growth_measure,
                annual_typical_growth_measure,
                completion_date,
                diagnostic_gain,
                `grouping`,
                measurement_and_data_scale_score,
                mid_on_grade_level_scale_score,
                most_recent_diagnostic_y_n,
                most_recent_diagnostic_ytd_y_n,
                number_and_operations_scale_score,
                overall_scale_score,
                percentile,
                `start_date`,
                `subject`
            ),

            cast(_dagster_partition_academic_year as int) as academic_year_int,
            cast(annual_stretch_growth_measure as int) as annual_stretch_growth_measure,
            cast(annual_typical_growth_measure as int) as annual_typical_growth_measure,
            cast(diagnostic_gain as int) as diagnostic_gain,
            cast(`grouping` as int) as `grouping`,
            cast(
                measurement_and_data_scale_score as int
            ) as measurement_and_data_scale_score,
            cast(
                mid_on_grade_level_scale_score as int
            ) as mid_on_grade_level_scale_score,
            cast(
                number_and_operations_scale_score as int
            ) as number_and_operations_scale_score,
            cast(overall_scale_score as int) as overall_scale_score,
            cast(percentile as int) as percentile,

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
