select
    a.studentsdcid,
    a.scorepoints,
    a.islate,
    a.isexempt,
    a.ismissing,
    a.assignmentsectionid,

    asec.assignmentid,
    asec.sectionsdcid,
from {{ ref("stg_powerschool__assignmentscore") }} as a
inner join
    {{ ref("stg_powerschool__assignmentsection") }} as asec
    on a.assignmentsectionid = asec.assignmentsectionid
