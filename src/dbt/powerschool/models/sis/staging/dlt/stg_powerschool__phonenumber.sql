select
    phonenumber,
    phonenumberext,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(phonenumberid as int) as phonenumberid,
    cast(issms as int) as issms,
from {{ source("powerschool_dlt", "phonenumber") }}
