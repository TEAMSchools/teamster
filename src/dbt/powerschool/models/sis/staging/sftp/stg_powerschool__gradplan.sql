{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    `name`,

    /* records */
    id.int_value as id,
    plantype.int_value as plantype,
from {{ source("powerschool", "src_powerschool__gradplan") }}
