select i.*, cfp.* except (incident_id),
from {{ ref("stg_deanslist__incidents") }} as i
left join
    {{ ref("int_deanslist__incidents__custom_fields__pivot") }} as cfp
    on i.incident_id = cfp.incident_id
