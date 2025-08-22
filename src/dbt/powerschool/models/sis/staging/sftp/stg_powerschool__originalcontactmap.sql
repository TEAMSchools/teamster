select
    * except (originalcontactmapid, studentcontactassocid, whencreated, whenmodified),

    cast(originalcontactmapid as int) as originalcontactmapid,
    cast(studentcontactassocid as int) as studentcontactassocid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__originalcontactmap") }}
