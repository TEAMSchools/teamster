select
    * except (
        countrycodesetid,
        countycodesetid,
        geocodelatitude,
        geocodelongitude,
        isverified,
        personaddressid,
        statescodesetid,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(countrycodesetid as int) as countrycodesetid,
    cast(countycodesetid as int) as countycodesetid,
    cast(isverified as int) as isverified,
    cast(personaddressid as int) as personaddressid,
    cast(statescodesetid as int) as statescodesetid,

    cast(geocodelatitude as numeric) as geocodelatitude,
    cast(geocodelongitude as numeric) as geocodelongitude,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__personaddress") }}
