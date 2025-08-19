{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    `name`,

    /* records */
    id.int_value as id,
    plantype.int_value as plantype,
from {{ source("powerschool", "src_powerschool__gradplan") }}
