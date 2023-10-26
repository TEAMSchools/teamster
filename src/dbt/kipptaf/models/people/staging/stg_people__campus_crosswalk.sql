select *, from {{ source("people", "src_people__campus_crosswalk") }}
