select *, from {{ source("powerschool_sftp", "src_powerschool__sced_code_mapping") }}
