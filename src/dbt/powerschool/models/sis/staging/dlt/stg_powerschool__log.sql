select
    `entry`,

    cast(dcid as int) as dcid,
    cast(studentid as int) as studentid,
    cast(logtypeid as int) as logtypeid,
    cast(entry_date as date) as entry_date,
from {{ source("powerschool_dlt", "log") }}
