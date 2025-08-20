select *,
from {{ source("powerschool_sftp", "src_powerschool__gpprogresssubjectearned") }}
