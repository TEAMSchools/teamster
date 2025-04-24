select
    coursenumber,
    -- whencreated,
    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    schedulerequestsdcid.int_value as schedulerequestsdcid,
    requestedcredits.double_value as requestedcredits,
from {{ source("powerschool", "src_powerschool__gpprogresssubjectrequested") }}
