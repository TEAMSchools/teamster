select
    `name`,
    `description`,
    psguid,
    importcode,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(testid as int) as testid,
    cast(sortorder as int) as sortorder,
from {{ source("powerschool_dlt", "testscore") }}
