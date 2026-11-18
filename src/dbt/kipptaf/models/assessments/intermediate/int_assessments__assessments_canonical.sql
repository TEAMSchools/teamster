with
    canonical_regions as (
        select
            m.source,
            rg.canonical_assessment_id,

            array_agg(distinct rg.region order by rg.region) as regions_array,
        from {{ ref("int_assessments__assessments_members") }} as m
        cross join unnest(m.region_groups) as rg
        group by m.source, rg.canonical_assessment_id
    )

select
    r.source,
    r.canonical_assessment_id,
    r.regions_array,

    p.title,
    p.administered_at as administered_date,
    p.subject_area,
    p.scope,
    p.module_code,
    p.academic_year,
    p.academic_year_clean,
    p.grade_level_id,

    p.grade_level_id - 1 as grade_level,
from canonical_regions as r
inner join
    {{ ref("int_assessments__assessments_members") }} as p
    on r.source = p.source
    and r.canonical_assessment_id = p.assessment_id
