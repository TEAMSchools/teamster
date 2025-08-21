select
    * except (day_number, dcid, id, schoolid, sortorder, year_id),

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(day_number as int) as day_number,
    cast(schoolid as int) as schoolid,
    cast(sortorder as int) as sortorder,
    cast(year_id as int) as year_id,
from {{ source("powerschool_sftp", "src_powerschool__cycle_day") }}
