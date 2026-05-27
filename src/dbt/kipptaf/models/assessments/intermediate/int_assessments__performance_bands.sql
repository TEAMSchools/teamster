with
    overall as (
        select
            assessment_id,
            performance_band_set_id,

            'overall' as response_type,
            -1 as response_type_id,
        from {{ ref("int_assessments__assessments_members") }}
    ),

    standards as (
        select
            assessment_id,
            standard_id as response_type_id,
            performance_band_set_id,

            'standard' as response_type,
        from {{ ref("stg_illuminate__dna_assessments__assessment_standards") }}
    ),

    reporting_groups as (
        select
            assessment_id,
            reporting_group_id as response_type_id,
            performance_band_set_id,

            'group' as response_type,
        from {{ ref("stg_illuminate__dna_assessments__assessments_reporting_groups") }}
    ),

    unioned as (
        select assessment_id, response_type, response_type_id, performance_band_set_id,
        from overall
        union all
        select assessment_id, response_type, response_type_id, performance_band_set_id,
        from standards
        union all
        select assessment_id, response_type, response_type_id, performance_band_set_id,
        from reporting_groups
    )

select
    u.assessment_id,
    u.response_type,
    u.response_type_id,
    u.performance_band_set_id,

    if(
        a.is_internal_assessment,
        first_value(u.performance_band_set_id) over (
            partition by
                a.is_internal_assessment,
                a.canonical_assessment_id,
                u.response_type,
                u.response_type_id
            order by u.assessment_id
        ),
        u.performance_band_set_id
    ) as canonical_performance_band_set_id,
from unioned as u
inner join
    {{ ref("int_assessments__assessments_members") }} as a
    on u.assessment_id = a.assessment_id
