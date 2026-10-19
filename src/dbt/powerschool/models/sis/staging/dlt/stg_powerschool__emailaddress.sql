select
    emailaddress,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(emailaddressid as int) as emailaddressid,
from {{ source("powerschool_dlt", "emailaddress") }}
