select
    `description`,
    gradelevels,

    /* records */
    id.int_value as id,
    gpversionid.int_value as gpversionid,
    sortorder.int_value as sortorder,
from {{ source("powerschool", "src_powerschool__gpselector") }}
