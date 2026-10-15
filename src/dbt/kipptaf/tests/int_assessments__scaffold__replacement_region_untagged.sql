-- Replacement students can only be reported against a region the assessment is
-- tagged for.
select
    sc.source,
    sc.assessment_id,
    sc.region,
    sc.powerschool_school_id,

    a.canonical_assessment_id,
from {{ ref("int_assessments__scaffold") }} as sc
inner join
    {{ ref("int_assessments__assessments_members") }} as a
    on sc.source = a.source
    and sc.assessment_id = a.assessment_id
inner join
    {{ ref("int_assessments__assessments_canonical") }} as c
    on a.source = c.source
    and a.canonical_assessment_id = c.canonical_assessment_id
where
    sc.is_internal_assessment
    and sc.is_replacement
    and not coalesce(sc.region in unnest(c.regions_array), false)
