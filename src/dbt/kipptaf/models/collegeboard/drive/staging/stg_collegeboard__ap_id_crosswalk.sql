select *, from {{ source("collegeboard", "src_collegeboard__ap_id_crosswalk") }}
