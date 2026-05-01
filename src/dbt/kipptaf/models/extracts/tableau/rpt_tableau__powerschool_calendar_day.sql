with
    schools_clean as (
        {# TODO: refactor lookup table #}
        /* powerschool_school_id not unique */
        select distinct
            location_powerschool_school_id as powerschool_school_id,
            location_region as region,
            location_clean_name as clean_name,
        from {{ ref("int_people__location_crosswalk") }}
    )

select cd.date_value, cd.insession, cd.schoolid, sc.region, sc.clean_name,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join schools_clean as sc on cd.schoolid = sc.powerschool_school_id
where cd.schoolid != 0
