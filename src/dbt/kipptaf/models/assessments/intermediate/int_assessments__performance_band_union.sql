with
    used_band_sets as (
        -- grain projection, not dup-masking: 1 row per source and band set
        select distinct source, performance_band_set_id,
        from {{ ref("int_assessments__response_rollup") }}
        where is_internal_assessment and performance_band_set_id is not null
    ),

    bands as (
        select
            performance_band_set_id,
            description as performance_band_set,
            label as band_label,
            minimum_value as minimum_score,
            is_mastery,

            'illuminate' as source,

            cast(label_number as int64) as band_number,
        from {{ ref("int_illuminate__performance_band_sets") }}

        union all

        select
            band_set_id as performance_band_set_id,
            band_set_name as performance_band_set,
            label as band_label,
            min_score as minimum_score,
            is_mastery,

            'apex' as source,

            label_number as band_number,
        from {{ ref("int_focus__apex_band_levels") }}
    ),

    set_attributes as (
        select
            b.source,
            b.performance_band_set_id,
            b.performance_band_set,
            b.band_label,
            b.band_number,
            b.minimum_score,
            b.is_mastery,

            count(*) over w_set as band_count,
            min(if(b.is_mastery, b.band_number, null)) over w_set
            as mastery_band_number,
            min(if(b.is_mastery, b.minimum_score, null)) over w_set
            as mastery_minimum_score,
            lead(b.minimum_score) over (w_set order by b.band_number) as maximum_score,
            row_number() over (w_set order by b.minimum_score) as cut_rank,
        from bands as b
        inner join
            used_band_sets as u
            on b.source = u.source
            and b.performance_band_set_id = u.performance_band_set_id
        window w_set as (partition by b.source, b.performance_band_set_id)
    ),

    band_checks as (
        select
            *,

            -- a band breaks the rule when its mastery flag disagrees with its
            -- position, it is out of cut-point order, or mastery starts below
            -- band 3; a null mastery band (no mastery band) breaks it too
            coalesce(
                is_mastery = (band_number >= mastery_band_number)
                and band_number = cut_rank
                and mastery_band_number >= 3,
                false
            ) as is_band_valid,
        from set_attributes
    ),

    set_checks as (
        select
            *,

            logical_and(is_band_valid) over (
                partition by source, performance_band_set_id
            ) as is_level_rule_valid,
        from band_checks
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["source", "performance_band_set_id", "band_number"]
        )
    }} as performance_band_key,

    source,
    performance_band_set_id,
    performance_band_set,
    band_label,
    band_number,
    band_count,
    minimum_score,
    maximum_score,
    is_mastery,
    mastery_band_number,
    mastery_minimum_score,
    is_level_rule_valid,

    if(is_level_rule_valid, band_number = 1 and not is_mastery, null) as is_far_below,

    case
        when not is_level_rule_valid
        then null
        when band_number >= mastery_band_number
        then 'At/Above'
        when band_number = mastery_band_number - 1
        then 'Approaching'
        else 'Below'
    end as mastery_level,
from set_checks
