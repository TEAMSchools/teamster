select
    `name`,
    clean_name,
    abbreviation,
    grade_band,
    region,
    powerschool_school_id,
    deanslist_school_id,
    reporting_school_id,
    is_campus,
    is_pathways,
    dagster_code_location,
    head_of_schools_employee_number,
from {{ source("people", "src_people__location_crosswalk") }}
