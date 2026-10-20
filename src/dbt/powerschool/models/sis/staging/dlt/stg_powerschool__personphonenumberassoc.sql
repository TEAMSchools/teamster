select
    phonenumberasentered,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(personphonenumberassocid as int) as personphonenumberassocid,
    cast(personid as int) as personid,
    cast(phonenumberid as int) as phonenumberid,
    cast(phonetypecodesetid as int) as phonetypecodesetid,
    cast(phonenumberpriorityorder as int) as phonenumberpriorityorder,
    cast(ispreferred as int) as ispreferred,
from {{ source("powerschool_dlt", "personphonenumberassoc") }}
