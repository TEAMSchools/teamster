select
    actualscoreentered,

    cast(assignmentscoreid as int) as assignmentscoreid,
    cast(assignmentsectionid as int) as assignmentsectionid,
    cast(isexempt as int) as isexempt,
    cast(islate as int) as islate,
    cast(ismissing as int) as ismissing,
    cast(studentsdcid as int) as studentsdcid,
    cast(scorepoints as float64) as scorepoints,
from {{ source("powerschool_dlt", "assignmentscore") }}
