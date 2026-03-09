select cast(studentsdcid as int) as studentsdcid, infosnap_id, media_release,
from {{ source("powerschool_sftp", "src_powerschool__u_studentsuserfields") }}
