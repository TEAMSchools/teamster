select
    `name`,
    psguid,

    cast(id as int) as id,
    cast(dcid as int) as dcid,
    cast(schoolid as int) as schoolid,
    cast(year_id as int) as year_id,
    cast(attendance_conversion_id as int) as attendance_conversion_id,
from {{ source("powerschool_dlt", "bell_schedule") }}
