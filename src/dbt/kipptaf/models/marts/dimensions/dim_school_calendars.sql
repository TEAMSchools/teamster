with
    locations as (
        select powerschool_school_id, dagster_code_location, location_name,
        from {{ ref("stg_people__locations") }}
    )

select
    cd.date_value as date_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }} as location_key,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_membership_day,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join
    locations as loc
    on cd.schoolid = loc.powerschool_school_id
    and {{ extract_code_location("cd") }} = loc.dagster_code_location
