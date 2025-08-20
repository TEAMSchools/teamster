select *, from {{ source("powerschool_sftp", "src_powerschool__s_nj_crs_x") }}
