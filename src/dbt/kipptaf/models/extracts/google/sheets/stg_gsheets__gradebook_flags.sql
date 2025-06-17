select *, from {{ source("google", "src_gsheets__gradebook_flags") }}
