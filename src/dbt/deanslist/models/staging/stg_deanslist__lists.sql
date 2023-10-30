select
    isdated as `is_dated`,
    nullif(listname, '') as `list_name`,
    safe_cast(nullif(listid, '') as int) as `list_id`,
from {{ source("deanslist", "src_deanslist__lists") }}
