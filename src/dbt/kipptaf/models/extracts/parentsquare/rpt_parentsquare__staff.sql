with
    schools as (
        -- Same filter as rpt_parentsquare__schools so a staff row can never
        -- reference a school the schools feed omits.
        select
            _dbt_source_project as code_location,

            cast(school_number as string) as school_id,
        from {{ ref("stg_powerschool__schools") }}
        where _dbt_source_project != 'kippmiami' and state_excludefromreporting = 0
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
        -- staff. The scoping below reduces it to regional-office Operations, and
        -- `code_location` carries each leader's region so the fan-out below stays
        -- inside it. LDAP join shape follows rpt_clever__staff.
        -- `google_email` (@apps.teamschools.org), NOT the roster's `mail` /
        -- `user_principal_name`, which are the AD/Exchange addresses
        -- (@kippnj.org, @kippteamandfamily.org). The two never coincide for any
        -- leader in this group, and ParentSquare authenticates these users
        -- through Google — so an AD address here syncs a staff user nobody can
        -- sign in as. This is where rpt_parentsquare__staff diverges from
        -- rpt_clever__staff, whose consumer matches on AD.
        select
            r.employee_number,
            r.job_title,
            r.given_name,
            r.family_name_1,
            r.google_email,
            r.home_work_location_dagster_code_location as code_location,
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
            and r.home_work_location_dagster_code_location != 'kippmiami'
            and r.home_work_location_powerschool_school_id = 0
            and r.home_department_name = 'Operations'
    )

select
    o.job_title as title,
    o.given_name as first_name,
    o.family_name_1 as last_name,
    o.google_email as email,

    s.school_id,
    s.code_location,

    cast(o.employee_number as string) as staff_id,
from ops_leaders as o
inner join schools as s on o.code_location = s.code_location
