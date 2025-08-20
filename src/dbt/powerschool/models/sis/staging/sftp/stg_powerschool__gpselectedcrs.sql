select
    coursenumber,

    /* records */
    id.int_value as id,
    gpselectorid.int_value as gpselectorid,
from {{ source("powerschool_sftp", "src_powerschool__gpselectedcrs") }}
