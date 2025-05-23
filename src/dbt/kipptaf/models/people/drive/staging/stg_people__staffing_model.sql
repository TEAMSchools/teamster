select *, from {{ source("people", "src_people__staffing_model") }}
