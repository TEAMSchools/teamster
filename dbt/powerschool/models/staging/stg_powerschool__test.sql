select
    * except (dcid, id, test_type),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    test_type.int_value as test_type,
from {{ source("powerschool", "src_powerschool__test") }}
