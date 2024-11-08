select
    dcid.int_value as dcid,
    id.int_value as id,
    studentid.int_value as studentid,
    testscoreid.int_value as testscoreid,
    studenttestid.int_value as studenttestid,
    numscore.double_value as numscore,
    percentscore.double_value as percentscore,
    readonly.int_value as `readonly`,
    alphascore,
    psguid,
    notes,
from {{ source("powerschool", "src_powerschool__studenttestscore") }}
