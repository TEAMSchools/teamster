select
    `name`,
    rolekey,
    `description`,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    productname,

    cast(id as int) as id,
    cast(rolemoduleid as int) as rolemoduleid,
    cast(islocked as int) as islocked,
    cast(isvisible as int) as isvisible,
    cast(isenabled as int) as isenabled,
    cast(sortorder as int) as sortorder,
from {{ source("powerschool_dlt", "roledef") }}
