with
    schools_clean as (
        select powerschool_school_id, region, clean_name,
        from {{ ref("stg_people__location_crosswalk") }}
        group by powerschool_school_id, region, clean_name
    )

select cd.date_value, cd.insession, cd.schoolid, sc.region, sc.clean_name,
from {{ ref("stg_powerschool__calendar_day") }} as cd
join schools_clean as sc on cd.schoolid = sc.powerschool_school_id
where schoolid != 0
