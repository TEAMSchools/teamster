select *, from {{ source("kippadb", "src_kippadb__nsc_crosswalk") }}
