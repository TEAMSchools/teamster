select
    * except (dcid, id, schoolid, year_id, day_number, sortorder),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    year_id.int_value as year_id,
    day_number.int_value as day_number,
    sortorder.int_value as sortorder,
from {{ source("powerschool", "src_powerschool__cycle_day") }}
