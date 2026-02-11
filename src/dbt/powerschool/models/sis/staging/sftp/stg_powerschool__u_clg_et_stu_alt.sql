select * except (source_file_name),
from {{ source("powerschool_sftp", "src_powerschool__u_clg_et_stu_alt") }}
