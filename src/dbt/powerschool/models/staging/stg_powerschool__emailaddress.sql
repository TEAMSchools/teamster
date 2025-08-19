select
    * except (emailaddressid),

    /* column transformations */
    emailaddressid.int_value as emailaddressid,
from {{ source("powerschool", "src_powerschool__emailaddress") }}
