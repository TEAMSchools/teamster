select * from {{ source("people", "src_people__location_crosswalk") }}
