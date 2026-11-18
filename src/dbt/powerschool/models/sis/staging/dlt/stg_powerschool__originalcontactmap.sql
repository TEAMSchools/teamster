select
    originalcontacttype,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(originalcontactmapid as int) as originalcontactmapid,
    cast(studentcontactassocid as int) as studentcontactassocid,
from {{ source("powerschool_dlt", "originalcontactmap") }}
