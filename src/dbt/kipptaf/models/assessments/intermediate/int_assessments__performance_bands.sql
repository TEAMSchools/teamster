with
    overall as (
        select
            assessment_id,
            performance_band_set_id,

            'overall' as response_type,
            '-1' as merge_key,
            -1 as response_type_id,
        from {{ ref("int_assessments__assessments_members") }}
        where source = 'illuminate'
    ),

    standards as (
        select
            ast.assessment_id,
            ast.standard_id as response_type_id,
            ast.performance_band_set_id,

            'standard' as response_type,

            -- Illuminate copies a standard into several standards sets, so one
            -- standard can arrive as 2 records with the same code and text
            format('%T|%T', std.custom_code, std.description) as merge_key,
        from {{ ref("stg_illuminate__dna_assessments__assessment_standards") }} as ast
        inner join
            {{ ref("stg_illuminate__standards__standards") }} as std
            on ast.standard_id = std.standard_id
    ),

    reporting_groups as (
        select
            assessment_id,
            reporting_group_id as response_type_id,
            performance_band_set_id,

            'group' as response_type,

            cast(reporting_group_id as string) as merge_key,
        from {{ ref("stg_illuminate__dna_assessments__assessments_reporting_groups") }}
    ),

    unioned as (
        select
            assessment_id,
            response_type,
            response_type_id,
            performance_band_set_id,
            merge_key,
        from overall
        union all
        select
            assessment_id,
            response_type,
            response_type_id,
            performance_band_set_id,
            merge_key,
        from standards
        union all
        select
            assessment_id,
            response_type,
            response_type_id,
            performance_band_set_id,
            merge_key,
        from reporting_groups
    ),

    grouped as (
        select
            u.assessment_id,
            u.response_type,
            u.response_type_id,
            u.performance_band_set_id,

            a.is_internal_assessment,

            min(u.response_type_id) over w_merge as canonical_response_type_id,
            max(u.response_type_id) over w_merge as max_response_type_id,
            min(u.performance_band_set_id) over w_merge as min_band_set_id,
            max(u.performance_band_set_id) over w_merge as max_band_set_id,
            countif(u.performance_band_set_id is null) over w_merge as n_null_band_sets,
            first_value(u.performance_band_set_id) over (
                w_merge order by u.assessment_id, u.response_type_id
            ) as first_band_set_id,
        from unioned as u
        inner join
            {{ ref("int_assessments__assessments_members") }} as a
            on u.assessment_id = a.assessment_id
        where a.source = 'illuminate'
        window
            w_merge as (
                partition by
                    a.is_internal_assessment,
                    if(
                        a.is_internal_assessment,
                        a.canonical_assessment_id,
                        u.assessment_id
                    ),
                    u.response_type,
                    u.merge_key
            )
    )

select
    assessment_id,
    response_type,
    response_type_id,
    performance_band_set_id,
    canonical_response_type_id,

    case
        -- one standard split across records on different band sets: no single
        -- set can label the merged score (min/max skip nulls, so count them)
        when
            canonical_response_type_id != max_response_type_id
            and (min_band_set_id != max_band_set_id or n_null_band_sets > 0)
        then null
        when is_internal_assessment
        then first_band_set_id
        else performance_band_set_id
    end as canonical_performance_band_set_id,
from grouped
