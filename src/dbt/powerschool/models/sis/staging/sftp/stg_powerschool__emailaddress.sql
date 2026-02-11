select
    * except (emailaddressid, whencreated, whenmodified, source_file_name),

    cast(emailaddressid as int) as emailaddressid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__emailaddress") }}
