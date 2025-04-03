select
    coursenumber,
    lettergrade,
    -- whencreated,
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    storedgradesdcid.int_value as storedgradesdcid,
    earnedcredits.double_value as earnedcredits,
    percentgrade.double_value as percentgrade,
from {{ source("powerschool", "src_powerschool__gpprogresssubjectearned") }}
