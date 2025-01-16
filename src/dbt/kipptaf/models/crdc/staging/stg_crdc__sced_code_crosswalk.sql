select *, from {{ source("crdc", "src_crdc__sced_code_crosswalk") }}
