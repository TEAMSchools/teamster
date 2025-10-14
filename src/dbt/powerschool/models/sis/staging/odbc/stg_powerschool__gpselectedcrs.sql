select
    coursenumber,

    /* records */
    id.int_value as id,
    gpselectorid.int_value as gpselectorid,
from {{ source("powerschool_odbc", "src_powerschool__gpselectedcrs") }}
