-- The gated Tableau location values are a hardcoded, known set, each with a
-- matching KNJ-SG-Tableau All Staff group. This asserts the SET, not a count:
-- a bare cardinality check stays green if a new campus opens in the same
-- period the last active staffer leaves another location (count holds at 30
-- while the new location silently gates to nothing in Tableau). Fails on any
-- active location_clean_name outside this list, and on any listed value with
-- no currently active staff. Update this list in the same change that
-- creates or retires a Tableau group for a location.
with
    expected_locations as (
        select location_clean_name,
        from
            unnest(
                [
                    'KIPP BOLD Academy',
                    'KIPP Cooper Norcross High',
                    'KIPP Courage Academy',
                    'KIPP Hatch Middle',
                    'KIPP Justice Academy',
                    'KIPP Lanning Square Middle',
                    'KIPP Lanning Square Primary',
                    'KIPP Legacy Elementary',
                    'KIPP Legacy Middle',
                    'KIPP Life Academy',
                    'KIPP Miami - North Campus',
                    'KIPP Miami - Poinciana Campus',
                    'KIPP Miami Technical High',
                    'KIPP Newark Collegiate Academy',
                    'KIPP Newark Lab High School',
                    'KIPP Purpose Academy',
                    'KIPP Rise Academy',
                    'KIPP Royalty Academy',
                    'KIPP SPARK Academy',
                    'KIPP Seek Academy',
                    'KIPP Sumner Elementary',
                    'KIPP TEAM Academy',
                    'KIPP THRIVE Academy',
                    'KIPP Upper Roseville Academy',
                    'Paterson Prep Elementary School',
                    'Paterson Prep Middle School',
                    'Room 10',
                    'Room 11',
                    'Room 12',
                    'Room 9'
                ]
            ) as location_clean_name
    ),

    active_locations as (
        select distinct lc.location_clean_name,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("int_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.location_name
        where sr.assignment_status is distinct from 'Terminated'
    )

select
    coalesce(
        expected_locations.location_clean_name, active_locations.location_clean_name
    ) as location_clean_name,
from expected_locations
full join
    active_locations
    on expected_locations.location_clean_name = active_locations.location_clean_name
where
    expected_locations.location_clean_name is null
    or active_locations.location_clean_name is null
