select *,
from {{ source("powerschool_sftp", "src_powerschool__attendance_conversion_items") }}
