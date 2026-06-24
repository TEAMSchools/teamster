select
    cd.date_value as date_key,

    sch.location_key,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_membership_day,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join
    {{ ref("stg_powerschool__schools") }} as sch
    on cd.schoolid = sch.school_number
    and cd._dbt_source_project = sch._dbt_source_project
    and sch.location_key is not null
where cd.date_value is not null
