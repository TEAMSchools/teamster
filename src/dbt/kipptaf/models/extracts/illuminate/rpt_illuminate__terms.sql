-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    t.schoolid as `01 Site ID`,
    t.name as `02 Term Name`,
    t.id as `03 Term Num`,
    t.firstday as `04 Start Date`,
    t.lastday as `05 End Date`,
    t.portion as `06 Term Type`,

    if(t.name like '%Summer%', 2, 1 end) as `07 Session Type ID`,

    concat((t.yearid + 1990), '-', (t.yearid + 1991)) as `08 Academic Year`,

    t.dcid as `09 Local Term ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("stg_powerschool__terms") }} as t
