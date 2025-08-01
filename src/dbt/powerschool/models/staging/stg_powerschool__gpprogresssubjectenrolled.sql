select
    coursenumber,

    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    ccdcid.int_value as ccdcid,
    enrolledcredits.double_value as enrolledcredits,
from {{ source("powerschool", "src_powerschool__gpprogresssubjectenrolled") }}
