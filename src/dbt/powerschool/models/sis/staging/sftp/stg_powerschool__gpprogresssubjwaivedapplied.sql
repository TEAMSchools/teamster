{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    /* records */
    id.int_value as id,
    gpprogresssubjectid.int_value as gpprogresssubjectid,
    gpstudentwaiverid.int_value as gpstudentwaiverid,
    appliedcredits.double_value as appliedcredits,
from {{ source("powerschool_sftp", "src_powerschool__gpprogresssubjwaivedapplied") }}
