with
    canonical_picks as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_assessments__assessments_members"),
                partition_by="source, tag_group_assessment_id",
                order_by="assessment_id",
            )
        }}
    ),

    canonical_regions as (
        select
            source,
            tag_group_assessment_id,

            array_agg(distinct region) as regions_array,
        from
            {{ ref("int_assessments__assessments_members") }},
            unnest(regions_assessed_array) as region
        where is_internal_assessment
        group by source, tag_group_assessment_id
    )

select
    p.source,
    p.tag_group_assessment_id as canonical_assessment_id,
    p.title,
    p.administered_at as administered_date,
    p.subject_area,
    p.scope,
    p.module_code,
    p.academic_year,
    p.academic_year_clean,
    p.grade_level_id,

    coalesce(r.regions_array, []) as regions_array,

    p.grade_level_id - 1 as grade_level,
from canonical_picks as p
left join
    canonical_regions as r
    on p.source = r.source
    and p.tag_group_assessment_id = r.tag_group_assessment_id
where p.is_internal_assessment
