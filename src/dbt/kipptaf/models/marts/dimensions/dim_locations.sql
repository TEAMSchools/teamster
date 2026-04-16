-- TODO: int_people__location_crosswalk has duplicate rows (#3633)
select distinct
    {{ dbt_utils.generate_surrogate_key(["location_clean_name"]) }} as location_key,

    location_clean_name as location_name,
    coalesce(location_abbreviation, location_clean_name) as abbreviation,
    location_region as region,
    location_grade_band as grade_band,
    campus_name as campus,
    location_is_campus as is_campus,
    location_powerschool_school_id as powerschool_school_id,
    location_deanslist_school_id as deanslist_school_id,
from {{ ref("int_people__location_crosswalk") }}
where not location_is_pathways and location_clean_name <> 'KIPP Whittier Elementary'
