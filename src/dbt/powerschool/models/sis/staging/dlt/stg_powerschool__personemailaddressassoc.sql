select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(personemailaddressassocid as int) as personemailaddressassocid,
    cast(personid as int) as personid,
    cast(emailaddressid as int) as emailaddressid,
    cast(emailtypecodesetid as int) as emailtypecodesetid,
    cast(isprimaryemailaddress as int) as isprimaryemailaddress,
    cast(emailaddresspriorityorder as int) as emailaddresspriorityorder,
from {{ source("powerschool_dlt", "personemailaddressassoc") }}
