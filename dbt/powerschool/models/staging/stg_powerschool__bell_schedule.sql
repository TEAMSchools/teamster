select
    * except (dcid, id, schoolid, year_id, attendance_conversion_id),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    year_id.int_value as year_id,
    attendance_conversion_id.int_value as attendance_conversion_id,
from {{ source("powerschool", "src_powerschool__bell_schedule") }}
