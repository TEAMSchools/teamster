select *, from {{ source("powerschool_sftp", "src_powerschool__u_studentsuserfields") }}
