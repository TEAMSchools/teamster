select * except (source_file_name),
from {{ source("powerschool_sftp", "src_powerschool__gradescaleitem") }}
