-- Every active staff location must resolve to a Grow school by exact name.
-- The roster CTE inner-joins on this, so an unmatched location silently drops a
-- whole school's staff from the extract. Because the school PUT replaces
-- observationGroups, admins and assistantAdmins wholesale, those staff are then
-- stripped from all three lists in Grow. A school renamed in the Grow UI is the
-- likely cause.
select sr.home_work_location_reporting_name, count(*) as staff_ct,
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("stg_schoolmint_grow__schools") }} as sch
    on sr.home_work_location_reporting_name = sch.name
where
    sr.assignment_status in ('Active', 'Leave')
    and sr.home_work_location_dagster_code_location != 'kipppaterson'
    and sr.home_work_location_reporting_name is not null
    and sch.name is null
group by 1
