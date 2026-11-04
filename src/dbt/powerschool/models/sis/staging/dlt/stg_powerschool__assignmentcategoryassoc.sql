select
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    ip_address,
    whomodifiedtype,
    transaction_date,
    executionid,

    cast(assignmentcategoryassocid as int) as assignmentcategoryassocid,
    cast(assignmentsectionid as int) as assignmentsectionid,
    cast(teachercategoryid as int) as teachercategoryid,
    cast(yearid as int) as yearid,
    cast(isprimary as int) as isprimary,
    cast(whomodifiedid as int) as whomodifiedid,
from {{ source("powerschool_dlt", "assignmentcategoryassoc") }}
