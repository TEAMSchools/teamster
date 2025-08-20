{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    coursenumber,
    lettergrade,
    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    storedgradesdcid.int_value as storedgradesdcid,
    earnedcredits.double_value as earnedcredits,
    percentgrade.double_value as percentgrade,
from {{ source("powerschool_sftp", "src_powerschool__gpprogresssubjectearned") }}
