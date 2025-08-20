select
    * except (dcid, id, studentid),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    studentid.int_value as studentid,
from {{ source("powerschool_sftp", "src_powerschool__studentrace") }}
