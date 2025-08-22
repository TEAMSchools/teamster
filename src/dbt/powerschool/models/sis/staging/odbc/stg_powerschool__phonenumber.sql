select
    * except (phonenumberid, issms),

    /* column transformations */
    phonenumberid.int_value as phonenumberid,
    issms.int_value as issms,
from {{ source("powerschool_odbc", "src_powerschool__phonenumber") }}
