select
    letter,
    abbreviation,
    day_name,
    psguid,

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(year_id as int) as year_id,
    cast(day_number as int) as day_number,
    cast(sortorder as int) as sortorder,
from {{ source("powerschool_dlt", "cycle_day") }}
