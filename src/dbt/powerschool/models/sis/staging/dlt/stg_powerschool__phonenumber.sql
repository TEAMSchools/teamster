-- a bare `phonenumber` binds to the whole-row struct of the same-named table
with source as (select *, from {{ source("powerschool_dlt", "phonenumber") }})

select
    phonenumber,
    phonenumberext,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(phonenumberid as int) as phonenumberid,
    cast(issms as int) as issms,
from source
