select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(startdate as date) as startdate,
    cast(enddate as date) as enddate,
    cast(personaddressassocid as int) as personaddressassocid,
    cast(personid as int) as personid,
    cast(personaddressid as int) as personaddressid,
    cast(addresstypecodesetid as int) as addresstypecodesetid,
    cast(addresspriorityorder as int) as addresspriorityorder,
from {{ source("powerschool_dlt", "personaddressassoc") }}
