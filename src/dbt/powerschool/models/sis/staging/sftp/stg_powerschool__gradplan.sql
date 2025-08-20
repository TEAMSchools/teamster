select
    `name`,

    /* records */
    id.int_value as id,
    plantype.int_value as plantype,
from {{ source("powerschool_sftp", "src_powerschool__gradplan") }}
