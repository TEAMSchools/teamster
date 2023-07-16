select
    t.schoolid as `01 Site ID`,
    t.`name` as `02 Term Name`,
    t.id as `03 Term Num`,
    t.firstday as `04 Start Date`,
    t.lastday as `05 End Date`,
    t.portion as `06 Term Type`,
    case when t.`name` like '%Summer%' then 2 else 1 end as `07 Session Type ID`,
    concat((t.yearid + 1990), '-', (t.yearid + 1991)) as `08 Academic Year`,
    t.dcid as `09 Local Term ID`
from {{ ref("stg_powerschool__terms") }} as t
inner join
    {{ ref("stg_powerschool__schools") }} as s
    on t.schoolid = s.school_number
    and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
    and s.state_excludefromreporting = 0
