{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    * except (
        countrycodesetid,
        countycodesetid,
        geocodelatitude,
        geocodelongitude,
        isverified,
        personaddressid,
        statescodesetid
    ),

    /* column transformations */
    countrycodesetid.int_value as countrycodesetid,
    countycodesetid.int_value as countycodesetid,
    isverified.int_value as isverified,
    personaddressid.int_value as personaddressid,
    statescodesetid.int_value as statescodesetid,

    geocodelatitude.bytes_decimal_value as geocodelatitude,
    geocodelongitude.bytes_decimal_value as geocodelongitude,
from {{ source("powerschool_odbc", "src_powerschool__personaddress") }}
