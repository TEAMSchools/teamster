with
    transformations as (
        select
            * except (dcid, id, quarter, week_number, cnt_w, cnt_h, cnt_f, cnt_s),

            /* column transformations */
            dcid.int_value as dcid,
            id.int_value as id,
            quarter.int_value as quarter,
            week_number.int_value as week_number,
            cnt_w.int_value as cnt_w,
            cnt_h.int_value as cnt_h,
            cnt_f.int_value as cnt_f,
            cnt_s.int_value as cnt_s,
        from {{ source("powerschool_odbc", "src_powerschool__u_expectations") }}
    )

select *
from transformations
