select
    safe_cast(nullif(listid, '') as int) as `list_id`,
    nullif(listname, '') as `list_name`,
    isdated as `is_dated`,
from {{ source("deanslist", "src_deanslist__lists") }}
