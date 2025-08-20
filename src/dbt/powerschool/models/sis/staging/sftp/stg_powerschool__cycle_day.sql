select *, from {{ source("powerschool_sftp", "src_powerschool__cycle_day") }}
