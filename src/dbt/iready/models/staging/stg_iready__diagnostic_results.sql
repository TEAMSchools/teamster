{% set src_model = source("iready", "src_iready__diagnostic_results") %}

select
    {{
        dbt_utils.star(
            from=src_model,
            except=[
                "student_grade",
                "completion_date",
                "start_date",
                "most_recent_diagnostic_y_n",
                "most_recent_diagnostic_ytd_y_n",
            ],
        )
    }},

    coalesce(
        most_recent_diagnostic_y_n, most_recent_diagnostic_ytd_y_n
    ) as most_recent_diagnostic_ytd_y_n,
    coalesce(
        student_grade.string_value, safe_cast(student_grade.long_value as string)
    ) as student_grade,
    parse_date('%m/%d/%Y', start_date) as start_date,
    parse_date('%m/%d/%Y', completion_date) as completion_date,
    safe_cast(left(academic_year, 4) as int) as academic_year_int,
    overall_scale_score
    + annual_typical_growth_measure as overall_scale_score_plus_typical_growth,
    overall_scale_score
    + annual_stretch_growth_measure as overall_scale_score_plus_stretch_growth,
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
from {{ src_model }}
