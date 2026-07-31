with
    schools as (
        -- Same filter as rpt_parentsquare__schools so a staff row can never
        -- reference a school the schools feed omits.
        select cast(school_number as string) as school_id,
        from {{ ref("stg_powerschool__schools") }}
        where _dbt_source_project = 'kippnewark' and state_excludefromreporting = 0
    ),

    ops_leaders as (
        -- The ParentSquare user population is the regional Operations leadership
        -- (Integration Planner question 4: "Regional Operation leaders ... No
        -- school staff, no teachers, etc"). Membership comes from the
        -- hand-curated `TS-DL-Regional Ops Leaders` distribution list rather than
        -- a hardcoded roster of individuals, so Ops owns the list and it tracks
        -- role changes without a code change. No job-title or job-function rule
        -- reproduces it: the regional Operations group holds twelve people across
        -- eight titles, and `job_function` is null for one Managing Director of
        -- School Operations who shares a title with two included peers — a data
        -- gap that would silently add or drop them.
        --
        -- The group spans all four regions and both regional and school-based
        -- staff, so the scoping below is what reduces it to Newark regional
        -- Operations. LDAP join shape follows rpt_clever__staff.
        select r.employee_number, r.job_title, r.given_name, r.family_name_1, r.mail,
        from {{ ref("stg_ldap__group") }} as g
        cross join unnest(g.member) as group_member_distinguished_name
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on group_member_distinguished_name = up.distinguished_name
        inner join
            {{ ref("int_people__staff_roster") }} as r
            on up.employee_number = r.employee_number
        where
            g.cn = 'TS-DL-Regional Ops Leaders'
            and r.worker_status_code != 'Terminated'
            and not r.is_prestart
            and r.home_work_location_dagster_code_location = 'kippnewark'
            and r.home_work_location_powerschool_school_id = 0
            and r.home_department_name = 'Operations'
    )

-- One row per (leader, school). ParentSquare's staff file is per-school and its
-- spec states a staff member "can be at more than one school", so fanning the
-- leaders across every Newark school is what grants them school-level access
-- everywhere — and it is what makes every rpt_parentsquare__sections.staff_id
-- resolve at its own school. No district-office row is emitted because
-- schools.csv carries only the twelve operating schools, so a school_id of 0
-- would dangle.
select
    o.job_title as title,
    o.given_name as first_name,
    o.family_name_1 as last_name,
    o.mail as email,

    s.school_id,

    cast(o.employee_number as string) as staff_id,
from ops_leaders as o
cross join schools as s
