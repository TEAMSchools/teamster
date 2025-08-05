select *, from {{ source("collegeboard", "src_collegeboard__sat_id_crosswalk") }}
