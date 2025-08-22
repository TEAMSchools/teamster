select
    * except (
        `date`,
        date2,
        dcid,
        id,
        schoolid,
        sortorder,
        spedindicator,
        time1,
        time2,
        value_x,
        valueli,
        valueli2,
        valueli3,
        valueli4,
        valuer,
        valuer2,
        yearid
    ),

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(schoolid as int) as schoolid,
    cast(sortorder as int) as sortorder,
    cast(spedindicator as int) as spedindicator,
    cast(time1 as int) as time1,
    cast(time2 as int) as time2,
    cast(valueli as int) as valueli,
    cast(valueli2 as int) as valueli2,
    cast(valueli3 as int) as valueli3,
    cast(valueli4 as int) as valueli4,
    cast(yearid as int) as yearid,

    cast(valuer as float64) as valuer,
    cast(valuer2 as float64) as valuer2,

    cast(`date` as date) as date_value,
    cast(date2 as date) as date2,

    cast(value_x as bytes) as value_x,
from {{ source("powerschool_sftp", "src_powerschool__gen") }}
