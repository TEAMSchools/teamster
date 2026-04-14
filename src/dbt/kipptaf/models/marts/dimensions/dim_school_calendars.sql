with
    locations as (
        -- TODO: int_people__location_crosswalk has duplicate rows upstream
        select distinct
            location_powerschool_school_id,
            location_dagster_code_location,
            location_clean_name,
            location_is_pathways,
        from {{ ref("int_people__location_crosswalk") }}
    )

select
    cd.date_value as date_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }} as location_key,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_membership_day,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join
    locations as loc
    on cd.schoolid = loc.location_powerschool_school_id
    and {{ extract_code_location("cd") }} = loc.location_dagster_code_location
where
    not loc.location_is_pathways
    and loc.location_clean_name <> 'KIPP Whittier Elementary'
