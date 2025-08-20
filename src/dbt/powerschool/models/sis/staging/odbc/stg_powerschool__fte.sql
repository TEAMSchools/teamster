{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (dcid, id, schoolid, yearid, fte_value),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    yearid.int_value as yearid,
    fte_value.double_value as fte_value,
from {{ source("powerschool_odbc", "src_powerschool__fte") }}
