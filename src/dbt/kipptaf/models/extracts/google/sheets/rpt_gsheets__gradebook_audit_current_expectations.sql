select
    id,
    school_level,
    `quarter`,
    week_number,
    cnt_w,
    cnt_h,
    cnt_f,
    cnt_s,
    notes,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    _dbt_source_project,

from {{ ref("stg_powerschool__u_expectations") }}
