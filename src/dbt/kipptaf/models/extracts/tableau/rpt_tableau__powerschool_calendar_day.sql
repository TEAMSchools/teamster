with
    schools_clean as (
        {# TODO: refactor lookup table #}
        /* powerschool_school_id not unique */
        select distinct powerschool_school_id, region, clean_name,
        from {{ ref("stg_google_sheets__people__location_crosswalk") }}
    )

select cd.date_value, cd.insession, cd.schoolid, sc.region, sc.clean_name,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join schools_clean as sc on cd.schoolid = sc.powerschool_school_id
where cd.schoolid != 0
