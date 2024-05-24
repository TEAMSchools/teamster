select *, from {{ source("surveys", "src_surveys__scd_answer_crosswalk") }}
