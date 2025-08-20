{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (
        personaddressid,
        statescodesetid,
        countrycodesetid,
        geocodelatitude,
        geocodelongitude
    ),

    /* column transformations */
    personaddressid.int_value as personaddressid,
    statescodesetid.int_value as statescodesetid,
    countrycodesetid.int_value as countrycodesetid,
    geocodelatitude.bytes_decimal_value as geocodelatitude,
    geocodelongitude.bytes_decimal_value as geocodelongitude,
from {{ source("powerschool_odbc", "src_powerschool__personaddress") }}
