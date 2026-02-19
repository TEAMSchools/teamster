select distinct
    location_clean_name as location_name,
    location_region,
    location_grade_band,
    location_powerschool_school_id,
    location_deanslist_school_id,
    location_is_campus,
    location_is_pathways,
    location_head_of_schools_employee_number,
    campus_name,

    coalesce(location_abbreviation, location_clean_name) as location_abbreviation,

    {{ dbt_utils.generate_surrogate_key(["location_clean_name"]) }} as locations_key,
from {{ ref("int_people__location_crosswalk") }}
where
    not location_is_campus
    and not location_is_pathways
    and location_clean_name <> 'KIPP Whittier Elementary'
