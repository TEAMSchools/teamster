select
    coursenumber,

    cast(id as int) as id,
    cast(gpprogresssubjectid as int) as gpprogresssubjectid,
    cast(ccdcid as int) as ccdcid,
    cast(enrolledcredits as float64) as enrolledcredits,
from {{ source("powerschool_dlt", "gpprogresssubjectenrolled") }}
