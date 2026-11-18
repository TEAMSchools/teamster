-- Scoped to the Focus era: Miami's frozen PowerSchool archive also fails this
-- condition (sentinel schoolids and empty school-years), which would bury the
-- Focus rows Ops needs to see.
select cd.schoolid, cd.yearid, count(*) as n_days,
from {{ ref("int_students__calendar_day") }} as cd
left join
    {{ ref("int_students__student_enrollment_union") }} as e
    on cd.schoolid = e.schoolid
    and cd.academic_year = e.academic_year
    and cd._dbt_source_project = e._dbt_source_project
where
    cd._dbt_source_project = 'kippmiami'
    and cd.academic_year >= 2026
    and e.schoolid is null
group by cd.schoolid, cd.yearid
