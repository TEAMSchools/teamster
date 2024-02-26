select *, from {{ source("powerschool", "src_powerschool__sced_code_mapping") }}
