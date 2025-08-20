{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    `description`,
    gradelevels,

    /* records */
    id.int_value as id,
    gpversionid.int_value as gpversionid,
    sortorder.int_value as sortorder,
from {{ source("powerschool_odbc", "src_powerschool__gpselector") }}
