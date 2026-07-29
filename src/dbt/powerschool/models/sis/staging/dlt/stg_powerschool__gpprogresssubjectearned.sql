select
    coursenumber,
    lettergrade,

    cast(id as int) as id,
    cast(gpprogresssubjectid as int) as gpprogresssubjectid,
    cast(storedgradesdcid as int) as storedgradesdcid,
    cast(earnedcredits as float64) as earnedcredits,
    cast(percentgrade as float64) as percentgrade,
from {{ source("powerschool_dlt", "gpprogresssubjectearned") }}
