select
    * except (
        dcid,
        id,
        valueli,
        valueli2,
        valuer,
        sortorder,
        schoolid,
        valueli3,
        valuer2,
        time1,
        time2,
        spedindicator,
        valueli4,
        yearid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    valueli.int_value as valueli,
    valueli2.int_value as valueli2,
    valuer.double_value as valuer,
    sortorder.int_value as sortorder,
    schoolid.int_value as schoolid,
    valueli3.int_value as valueli3,
    valuer2.double_value as valuer2,
    time1.int_value as time1,
    time2.int_value as time2,
    spedindicator.int_value as spedindicator,
    valueli4.int_value as valueli4,
    yearid.int_value as yearid,
from {{ source("powerschool", "src_powerschool__gen") }}
