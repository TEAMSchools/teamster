{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    credittype,

    /* records */
    id.int_value as id,
    gpselectorid.int_value as gpselectorid,
from {{ source("powerschool", "src_powerschool__gpselectedcrtype") }}
