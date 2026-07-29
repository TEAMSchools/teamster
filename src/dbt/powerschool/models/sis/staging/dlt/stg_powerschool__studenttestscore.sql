select
    alphascore,
    psguid,
    notes,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(studentid as int) as studentid,
    cast(testscoreid as int) as testscoreid,
    cast(studenttestid as int) as studenttestid,
    cast(numscore as float64) as numscore,
    cast(percentscore as float64) as percentscore,
    cast(`readonly` as int) as `readonly`,
from {{ source("powerschool_dlt", "studenttestscore") }}
