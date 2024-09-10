select *, from {{ source("powerschool", "src_powerschool__gradplan") }}
