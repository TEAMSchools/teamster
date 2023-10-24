select *, from {{ source("people", "src_people__powerschool_crosswalk") }}
