-- A relationship flagged as a caregiver whose related contact does NOT carry
-- Finalsite's adult status. Almost always this is correct and the related
-- person really is a student -- a sibling flagged `financial`, say -- and the
-- model's adult guard drops it as intended. The rows worth acting on are the
-- inverse: an adult whose own contact record was miskeyed with a student
-- status, whose relationship the guard then discards silently, because dense
-- ranking backfills the slot from another candidate and nothing else reports
-- the loss. Warn: each row is a Finalsite record to inspect, not a build
-- failure.
select
    r.finalsite_enrollment_id,
    r.rel_id,
    r.rel_type,
    c.status as related_contact_status,
    c.grade_name as related_contact_grade,
from {{ ref("stg_finalsite__contact_relationships") }} as r
inner join
    {{ ref("stg_finalsite__contacts") }} as c on r.rel_id = c.finalsite_enrollment_id
where
    (coalesce(r.is_primary, false) or coalesce(r.is_financial, false))
    and c.status != 'not_in_workflow'
