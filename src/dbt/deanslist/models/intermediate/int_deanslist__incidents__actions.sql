select
    i.incident_id,

    cast(nullif(a.said, '') as int) as said,
    cast(nullif(a.actionid, '') as int) as action_id,
    cast(nullif(a.sourceid, '') as int) as source_id,

    nullif(a.actionname, '') as action_name,
    nullif(a.pointvalue, '') as point_value,
from {{ ref("stg_deanslist__incidents") }} as i
cross join unnest(i.actions) as a
