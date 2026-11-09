select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(studentcontactassocid as int) as studentcontactassocid,
    cast(studentdcid as int) as studentdcid,
    cast(personid as int) as personid,
    cast(contactpriorityorder as int) as contactpriorityorder,
    cast(currreltypecodesetid as int) as currreltypecodesetid,
from {{ source("powerschool_dlt", "studentcontactassoc") }}
