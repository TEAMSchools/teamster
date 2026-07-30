-- Every active staff location must resolve to a canonical crosswalk name.
-- A new school added to ADP but not to the locations sheet lands here, and
-- would otherwise gate to nothing in the Tableau permissions block.
select sr.home_work_location_name, count(*) as staff_ct,
from {{ ref("int_people__staff_roster") }} as sr
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.location_name
where
    sr.assignment_status != 'Terminated'
    and sr.home_work_location_name is not null
    and lc.location_clean_name is null
group by 1
