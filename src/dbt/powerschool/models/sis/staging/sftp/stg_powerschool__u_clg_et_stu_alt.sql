select *, from {{ source("powerschool_sftp", "src_powerschool__u_clg_et_stu_alt") }}
