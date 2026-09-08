-- `primary` is a per-student singleton in Finalsite. The old model surfaced a
-- violation as a duplicate contact_1 failing the uniqueness test; dense ranking
-- absorbs a second primary into contact_2 instead, so the condition is tested
-- at the source where it can be acted on. No student trips this today -- it
-- guards against regression rather than reporting a backlog.
select finalsite_enrollment_id, count(*) as primary_relationships,
from {{ ref("stg_finalsite__contact_relationships") }}
where is_primary
group by finalsite_enrollment_id
having count(*) > 1
