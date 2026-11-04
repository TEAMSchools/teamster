select
    school_level,
    `quarter`,
    notes,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,

    cast(id as int) as id,
    cast(week_number as int) as week_number,
    cast(cnt_w as int) as cnt_w,
    cast(cnt_h as int) as cnt_h,
    cast(cnt_f as int) as cnt_f,
    cast(cnt_s as int) as cnt_s,
from {{ source("powerschool_dlt", "u_expectations") }}
