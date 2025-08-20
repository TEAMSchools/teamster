{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    studentid.int_value as studentid,
    logtypeid.int_value as logtypeid,
    entry_date,
    `entry`,
from {{ source("powerschool_odbc", "src_powerschool__log") }}
