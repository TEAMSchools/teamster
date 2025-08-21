select
    * except (lep_status, studentsdcid, whencreated, whenmodified),

    cast(lep_status as boolean) as lep_status,

    cast(studentsdcid as int) as studentsdcid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,

{# | is_homeless  |                 | BOOLEAN       | missing in definition | #}
from {{ source("powerschool_sftp", "src_powerschool__studentcorefields") }}
