select
    r.roster_id,
    r.roster_name,
    r.school_id,
    r.roster_type,
    r.active,

    a.student_school_id,
from {{ ref("stg_deanslist__rosters") }} as r
inner join
    {{ ref("stg_deanslist__roster_assignments") }} as a on r.roster_id = a.dl_roster_id
