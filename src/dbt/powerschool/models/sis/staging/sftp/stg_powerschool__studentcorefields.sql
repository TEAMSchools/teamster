select
    * except (lep_status, studentsdcid, whencreated, whenmodified),

    cast(studentsdcid as int) as studentsdcid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,

    if(homeless_code in ('Y1', 'Y2'), true, false) as is_homeless,
    if(lep_status in ('1', 'YES', 'Y'), true, false) as lep_status,
from {{ source("powerschool_sftp", "src_powerschool__studentcorefields") }}
