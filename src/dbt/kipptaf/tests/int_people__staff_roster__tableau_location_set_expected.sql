-- The gated location values are a known set of 30, each of which must have a
-- matching KNJ-SG-Tableau All Staff group. An addition should surface here
-- rather than silently gate to nothing in Tableau.
with
    expected as (
        select distinct lc.location_clean_name,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.location_name
        where sr.assignment_status != 'Terminated'
    )

select count(*) as location_ct,
from expected
having count(*) != 30
