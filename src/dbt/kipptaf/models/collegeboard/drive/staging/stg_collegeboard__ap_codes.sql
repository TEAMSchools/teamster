select *, from {{ source("collegeboard", "src_collegeboard__ap_codes") }}
