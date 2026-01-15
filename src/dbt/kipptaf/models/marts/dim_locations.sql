with
    location_crosswalk as (select *, from {{ ref("int_people__location_crosswalk") }})

    final as (
        select
            location_name,
            location_clean_name,
            location_region,
            location_abbreviation,
            location_grade_band,
            location_powerschool_school_id,
            location_deanslist_school_id,
            location_reporting_school_id,
            location_is_campus,
            location_is_pathways,
            location_dagster_code_location,
            location_head_of_schools_employee_number,
            campus_name,
        from location_crosswalk
    )

select *
from final
