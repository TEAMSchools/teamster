select
    `name`,
    `value`,
    psguid,
    ip_address,
    whomodifiedtype,
    transaction_date,
    executionid,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(yearid as int) as yearid,
    cast(userid as int) as userid,
    cast(whomodifiedid as int) as whomodifiedid,
from {{ source("powerschool_dlt", "prefs") }}
