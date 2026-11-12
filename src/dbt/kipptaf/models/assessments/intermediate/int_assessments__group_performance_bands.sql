with
    canonical_groups as (
        select
            canonical_assessment_id,
            tag_group_assessment_id,

            array_length(regions_array) > 0 as is_regional_group,
        from {{ ref("int_assessments__assessments_canonical") }}
        where source = 'illuminate'
    ),

    group_copies as (
        -- grain projection, not dup-masking: a copy whose regions share one
        -- group has one crosswalk row per region
        select distinct canonical_assessment_id, assessment_id,
        from {{ ref("int_assessments__assessment_region_groups") }}
        where source = 'illuminate'

        union all

        select cg.canonical_assessment_id, m.assessment_id,
        from canonical_groups as cg
        inner join
            {{ ref("int_assessments__assessments_members") }} as m
            on cg.tag_group_assessment_id = m.tag_group_assessment_id
            and m.source = 'illuminate'
        where not cg.is_regional_group

        union all

        select assessment_id as canonical_assessment_id, assessment_id,
        from {{ ref("int_assessments__assessments_members") }}
        where source = 'illuminate' and not is_internal_assessment
    ),

    group_records as (
        select
            gc.canonical_assessment_id,

            pb.response_type,
            pb.response_type_id,
            pb.performance_band_set_id,
            pb.canonical_response_type_id,

            first_value(pb.performance_band_set_id) over (
                partition by
                    gc.canonical_assessment_id,
                    pb.response_type,
                    pb.canonical_response_type_id
                order by pb.assessment_id asc, pb.response_type_id asc
            ) as first_band_set_id,
        from group_copies as gc
        inner join
            {{ ref("int_assessments__performance_bands") }} as pb
            on gc.assessment_id = pb.assessment_id
    )

select
    canonical_assessment_id,
    response_type,
    canonical_response_type_id as response_type_id,

    -- one standard split across records on different band sets: no single set
    -- can label the merged score (min/max skip nulls, so count them)
    if(
        min(response_type_id) != max(response_type_id)
        and (
            min(performance_band_set_id) != max(performance_band_set_id)
            or countif(performance_band_set_id is null) > 0
        ),
        null,
        any_value(first_band_set_id)
    ) as performance_band_set_id,
from group_records
group by canonical_assessment_id, response_type, canonical_response_type_id
