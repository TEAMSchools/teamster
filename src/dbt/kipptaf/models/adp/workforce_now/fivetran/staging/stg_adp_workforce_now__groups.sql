select
    * except (_fivetran_synced),
    `group` as group_code,

    coalesce(group_long_name, group_short_name) as `value`,
from {{ source("adp_workforce_now", "groups") }}
