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
        -- LDAP join shape follows rpt_clever__staff. The group spans both
        -- regions and school-based staff, so the filters below reduce it to
        -- regional-office Operations.
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
