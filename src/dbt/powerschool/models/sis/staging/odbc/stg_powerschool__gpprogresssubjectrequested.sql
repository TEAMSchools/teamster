{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    coursenumber,

    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    schedulerequestsdcid.int_value as schedulerequestsdcid,
    requestedcredits.double_value as requestedcredits,
from {{ source("powerschool_odbc", "src_powerschool__gpprogresssubjectrequested") }}
