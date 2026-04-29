select
    lc.name as location_name,

    pl.location_key,
    pl.location_name as location_clean_name,
    pl.abbreviation as location_abbreviation,
    pl.grade_band as location_grade_band,
    pl.location_region,
    pl.powerschool_school_id as location_powerschool_school_id,
    pl.deanslist_school_id as location_deanslist_school_id,
    pl.reporting_school_id as location_reporting_school_id,
    pl.is_campus as location_is_campus,
    pl.is_pathways as location_is_pathways,
    pl.dagster_code_location as location_dagster_code_location,
    pl.head_of_schools_employee_number as location_head_of_schools_employee_number,
    pl.campus_name,
from {{ ref("stg_google_sheets__people__location_crosswalk") }} as lc
left join
    {{ ref("stg_google_sheets__people__locations") }} as pl
    on lc.clean_name = pl.location_name
