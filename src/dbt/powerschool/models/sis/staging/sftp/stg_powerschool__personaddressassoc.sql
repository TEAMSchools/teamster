select
    * except (
        addresspriorityorder,
        addresstypecodesetid,
        personaddressassocid,
        personaddressid,
        personid,
        enddate,
        startdate,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(addresspriorityorder as int) as addresspriorityorder,
    cast(addresstypecodesetid as int) as addresstypecodesetid,
    cast(personaddressassocid as int) as personaddressassocid,
    cast(personaddressid as int) as personaddressid,
    cast(personid as int) as personid,

    cast(startdate as date) as startdate,
    cast(enddate as date) as enddate,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__personaddressassoc") }}
