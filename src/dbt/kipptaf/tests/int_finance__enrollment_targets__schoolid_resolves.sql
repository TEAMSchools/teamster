select et.schoolid,
from {{ ref("stg_google_sheets__finance__enrollment_targets") }} as et
left join
    {{ ref("stg_powerschool__schools") }} as sch on et.schoolid = sch.school_number
where sch.school_number is null
