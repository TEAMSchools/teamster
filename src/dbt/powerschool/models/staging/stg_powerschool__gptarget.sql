select
    /* records */
    id.int_value as id,
    gpselectorid.int_value as gpselectorid,
    gpnodeid.int_value as gpnodeid,
    sortorder.int_value as sortorder,
from {{ source("powerschool", "src_powerschool__gptarget") }}
