-- Focus in-session days at a school that enrolled nobody that year. Five Focus
-- schools carry unfiltered 212-day calendars including holidays and breaks; two
-- of them are closed but still map to live network location keys, so their days
-- reach dim_school_calendars. The fix belongs in Focus configuration, so this
-- warns rather than errors -- it makes the rows visible without hiding them.
select cd.schoolid, cd.yearid, count(*) as n_days,
from {{ ref("int_students__calendar_day") }} as cd
left join
    {{ ref("int_students__student_enrollment_union") }} as e
    on cd.schoolid = e.schoolid
    and cd.yearid = e.academic_year - 1990
    and cd._dbt_source_project = e._dbt_source_project
where cd._dbt_source_project = 'kippmiami' and e.schoolid is null
group by cd.schoolid, cd.yearid
