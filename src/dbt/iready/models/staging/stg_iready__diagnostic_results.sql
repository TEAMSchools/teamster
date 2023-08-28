select
    *,
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
from {{ source("iready", "src_iready__diagnostic_results") }}
where _dagster_partition_fiscal_year = safe_cast(right(academic_year, 4) as int)
