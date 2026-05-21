select
    cd.date_value as date_key,

    sch.location_key,

    cd.insession = 1 as is_in_session,
    cd.membershipvalue > 0 as is_membership_day,
from {{ ref("stg_powerschool__calendar_day") }} as cd
inner join
    {{ ref("stg_powerschool__schools") }} as sch
    on cd.schoolid = sch.school_number
    and {{ union_dataset_join_clause(left_alias="cd", right_alias="sch") }}
    and sch.location_key is not null
