select
    i.incident_id,

    nullif(a.actionname, '') as action_name,
    nullif(a.pointvalue, '') as point_value,

    safe_cast(nullif(a.said, '') as int) as said,
    safe_cast(nullif(a.actionid, '') as int) as action_id,
    safe_cast(nullif(a.sourceid, '') as int) as source_id,
from {{ ref("stg_deanslist__incidents") }} as i
cross join unnest(i.actions) as a
