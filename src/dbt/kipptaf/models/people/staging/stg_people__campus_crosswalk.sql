select
    `name`,
    location_name,
    region,
    grade_band,
    powerschool_school_id,
    reporting_school_id,
    abbreviation,
    is_pathways,
from {{ source("people", "src_people__campus_crosswalk") }}
