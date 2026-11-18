-- a bare `emailaddress` binds to the whole-row struct of the same-named table
with source as (select *, from {{ source("powerschool_dlt", "emailaddress") }})

select
    emailaddress,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(emailaddressid as int) as emailaddressid,
from source
