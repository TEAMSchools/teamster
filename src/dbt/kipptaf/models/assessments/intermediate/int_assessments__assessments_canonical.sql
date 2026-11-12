with
    group_regions as (
        select
            source,
            canonical_assessment_id,

            array_agg(distinct region order by region) as regions_array,
        from {{ ref("int_assessments__assessment_region_groups") }}
        group by source, canonical_assessment_id
    ),

    -- grain projection, not dup-masking: a tag group id that is also a
    -- regional group id is one group
    group_ids as (
        select source, canonical_assessment_id,
        from group_regions

        union distinct

        select source, tag_group_assessment_id as canonical_assessment_id,
        from {{ ref("int_assessments__assessments_members") }}
        where is_internal_assessment
    )

select
    g.source,
    g.canonical_assessment_id,

    m.tag_group_assessment_id,
    m.title,
    m.administered_at as administered_date,
    m.subject_area,
    m.scope,
    m.module_code,
    m.academic_year,
    m.academic_year_clean,
    m.grade_level_id,

    coalesce(r.regions_array, []) as regions_array,

    m.grade_level_id - 1 as grade_level,
from group_ids as g
inner join
    {{ ref("int_assessments__assessments_members") }} as m
    on g.source = m.source
    and g.canonical_assessment_id = m.assessment_id
left join
    group_regions as r
    on g.source = r.source
    and g.canonical_assessment_id = r.canonical_assessment_id
