-- Illuminate and Apex ids share one integer space, so a canonical pick must
-- resolve within its own source. A member whose (source, canonical id) has no
-- member with that (source, assessment id) was merged across sources.
select m.source, m.assessment_id, m.canonical_assessment_id,
from {{ ref("int_assessments__assessments_members") }} as m
left join
    {{ ref("int_assessments__assessments_members") }} as c
    on m.source = c.source
    and m.canonical_assessment_id = c.assessment_id
where c.assessment_id is null
