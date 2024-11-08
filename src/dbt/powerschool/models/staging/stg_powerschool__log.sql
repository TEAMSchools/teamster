select
    studentid.int_value as studentid,
    logtypeid.int_value as logtypeid,
    entry_date,
    `entry`,
from {{ source("powerschool", "src_powerschool__log") }}
