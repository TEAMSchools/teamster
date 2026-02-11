select
    * except (
        lep_status,
        studentsdcid,
        prevstudentid,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(studentsdcid as int) as studentsdcid,
    cast(prevstudentid as int) as prevstudentid,

    parse_timestamp('%m/%d/%Y', whencreated) as whencreated,
    parse_timestamp('%m/%d/%Y', whenmodified) as whenmodified,

    if(homeless_code in ('Y1', 'Y2'), true, false) as is_homeless,
    if(lep_status in ('1', 'YES', 'Y'), true, false) as lep_status,
from {{ source("powerschool_sftp", "src_powerschool__studentcorefields") }}
