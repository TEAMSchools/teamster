{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

{% set lep_status_true = ["1", "YES", "Y"] %}

select
    * except (studentsdcid, lep_status),

    /* column transformations */
    studentsdcid.int_value as studentsdcid,

    if(homeless_code in ('Y1', 'Y2'), true, false) as is_homeless,

    if(lep_status in unnest({{ lep_status_true }}), true, false) as lep_status,
from {{ source("powerschool_odbc", "src_powerschool__studentcorefields") }}
