select
    isdated as is_dated,

    cast(nullif(listid, '') as int) as list_id,

    nullif(listname, '') as list_name,
from {{ source("deanslist", "src_deanslist__lists") }}
