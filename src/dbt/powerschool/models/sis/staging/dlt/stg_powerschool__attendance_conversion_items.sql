select
    comment_value,
    conversion_mode_code,

    cast(id as int) as id,
    cast(dcid as int) as dcid,
    cast(attendance_conversion_id as int) as attendance_conversion_id,
    cast(input_value as int) as input_value,
    cast(attendance_value as float64) as attendance_value,
    cast(fteid as int) as fteid,
    cast(unused as int) as unused,
    cast(daypartid as int) as daypartid,
from {{ source("powerschool_dlt", "attendance_conversion_items") }}
