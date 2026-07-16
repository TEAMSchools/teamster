select
    * replace (
        cast(id as int) as id,
        cast(isenabled as int) as isenabled,
        cast(islocked as int) as islocked,
        cast(isvisible as int) as isvisible,
        cast(rolemoduleid as int) as rolemoduleid,
        cast(sortorder as int) as sortorder
    ),
from {{ source("powerschool_dlt", "roledef") }}
