select
    * except (
        attendance_conversion_id,
        attendance_value,
        daypartid,
        dcid,
        fteid,
        id,
        input_value,
        unused
    ),

    cast(attendance_conversion_id as int) as attendance_conversion_id,
    cast(daypartid as int) as daypartid,
    cast(dcid as int) as dcid,
    cast(fteid as int) as fteid,
    cast(id as int) as id,
    cast(input_value as int) as input_value,
    cast(unused as int) as unused,

    cast(attendance_value as float64) as attendance_value,

{# comment|missing in contract|
comment_value|STRING|missing in definition| #}
from {{ source("powerschool_sftp", "src_powerschool__attendance_conversion_items") }}
