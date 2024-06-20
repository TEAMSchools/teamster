select asec.*, a.studentsdcid, a.scorepoints, a.islate, a.isexempt, a.ismissing,
from {{ ref("int_powerschool__gradebook_assignments") }} as asec
left join
    {{ ref("stg_powerschool__assignmentscore") }} as a
    on asec.assignmentsectionid = a.assignmentsectionid
