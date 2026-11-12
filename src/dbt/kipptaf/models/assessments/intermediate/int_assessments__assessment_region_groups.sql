-- grain projection, not dup-masking: a region typed twice on one copy repeats
-- every column, and the window is fixed by (source, assessment_id, region)
select distinct
    m.source,
    m.assessment_id,
    m.tag_group_assessment_id,

    region,

    min(m.assessment_id) over (
        partition by m.source, m.tag_group_assessment_id, region
    ) as canonical_assessment_id,
from {{ ref("int_assessments__assessments_members") }} as m
cross join unnest(m.regions_assessed_array) as region
where m.is_internal_assessment
