select
    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    gpstudentwaiverid.int_value as gpstudentwaiverid,
    waivedcredits.double_value as waivedcredits,
from {{ source("powerschool", "src_powerschool__gpprogresssubjectwaived") }}
