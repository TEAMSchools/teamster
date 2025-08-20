{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (emailaddressid),

    /* column transformations */
    emailaddressid.int_value as emailaddressid,
from {{ source("powerschool_odbc", "src_powerschool__emailaddress") }}
