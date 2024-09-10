select *, from {{ source("powerschool", "src_powerschool__gpnode") }}
