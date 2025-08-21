select
    * except (issms, phonenumberid, whencreated, whenmodified),

    cast(issms as int) as issms,
    cast(phonenumberid as int) as phonenumberid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__phonenumber") }}
