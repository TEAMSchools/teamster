select
    * except (
        dcid,
        id,
        attendance_conversion_id,
        input_value,
        attendance_value,
        fteid,
        unused,
        daypartid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    attendance_conversion_id.int_value as attendance_conversion_id,
    input_value.int_value as input_value,
    attendance_value.double_value as attendance_value,
    fteid.int_value as fteid,
    unused.int_value as unused,
    daypartid.int_value as daypartid,
from {{ source("powerschool", "src_powerschool__attendance_conversion_items") }}
