select
    racecd,
    whocreated,
    whomodified,
    whencreated,
    whenmodified,
    psguid,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(studentid as int) as studentid,
from {{ source("powerschool_dlt", "studentrace") }}
