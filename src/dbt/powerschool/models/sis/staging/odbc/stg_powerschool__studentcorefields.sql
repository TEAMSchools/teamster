select
    * except (studentsdcid, lep_status),

    /* column transformations */
    studentsdcid.int_value as studentsdcid,

    if(homeless_code in ('Y1', 'Y2'), true, false) as is_homeless,
    if(lep_status in ('1', 'YES', 'Y'), true, false) as lep_status,
from {{ source("powerschool_odbc", "src_powerschool__studentcorefields") }}
