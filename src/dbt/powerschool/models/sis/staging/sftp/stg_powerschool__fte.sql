select
    * except (dcid, fte_value, id, schoolid, yearid),

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(yearid as int) as yearid,

    cast(fte_value as float64) as fte_value,
from {{ source("powerschool_sftp", "src_powerschool__fte") }}
