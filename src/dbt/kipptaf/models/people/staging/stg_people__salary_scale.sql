select *, from {{ source("people", "src_people__salary_scale") }}
