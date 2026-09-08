-- Focus in-session days at a school that enrolled nobody that year. Five Focus
-- schools carry unfiltered 212-day calendars including holidays and breaks; two
-- of them are closed but still map to live network location keys, so their days
-- reach dim_school_calendars. The fix belongs in Focus configuration, so this
-- warns rather than errors -- it makes the rows visible without hiding them.
--
-- Scoped to the Focus era, not to kippmiami as a whole. Miami's frozen PowerSchool
-- archive fails this same condition on 18 school-years -- sentinel schoolids 0 and
-- 999999 carrying a full 364 or 365 in-session days, plus a few real schools in
-- years they had no enrollment. That noise predates this model and is not what this
-- test is for; leaving it in buries the 2 rows Ops actually needs to see.
with
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    )

select cd.schoolid, cd.yearid, count(*) as n_days,
from {{ ref("int_students__calendar_day") }} as cd
cross join cutover as c
left join
    {{ ref("int_students__student_enrollment_union") }} as e
    on cd.schoolid = e.schoolid
    and cd.academic_year = e.academic_year
    and cd._dbt_source_project = e._dbt_source_project
where
    cd._dbt_source_project = 'kippmiami'
    and cd.academic_year >= c.focus_start_academic_year
    and e.schoolid is null
group by cd.schoolid, cd.yearid
