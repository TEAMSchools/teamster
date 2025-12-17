/* KNJ specific departments = all CMO schools */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    sr.powerschool_teacher_number as `01 Local User ID`,

    sch.school_number as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as sr
inner join
    {{ ref("stg_powerschool__schools") }} as sch on sch.state_excludefromreporting = 0
where
    sr.home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
    and sr.home_department_name in ('Teaching and Learning', 'Data', 'Executive')
    and sr.worker_status_code != 'Terminated'

union all

/* Campus-based staff = all schools at campus */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    sr.powerschool_teacher_number as `01 Local User ID`,

    cc.powerschool_school_id as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }} as sr
inner join
    {{ ref("stg_google_sheets__people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.name
    and not cc.is_pathways
where
    sr.worker_status_code != 'Terminated'
    and sr.home_department_name not in ('Teaching and Learning', 'Data', 'Executive')
    and sr.home_work_location_is_campus

union all

/* School-based staff = only respective school */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    powerschool_teacher_number as `01 Local User ID`,
    home_work_location_powerschool_school_id as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__staff_roster") }}
where
    worker_status_code != 'Terminated'
    and home_department_name not in ('Teaching and Learning', 'Data', 'Executive')
    and not home_work_location_is_campus

union all

/* Paterson = all schools in region */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    u.teachernumber as `01 Local User ID`,

    s.school_number as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("stg_powerschool__users") }} as u
inner join
    {{ ref("stg_powerschool__schools") }} as s
    on {{ union_dataset_join_clause(left_alias="u", right_alias="s") }}
    and s.state_excludefromreporting = 0
where
    u._dbt_source_relation like '%kipppaterson%' and (u.ptaccess = 1 or u.psaccess = 1)

union all

/* Temps */
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    employee_id as `01 Local User ID`,
    powerschool_school_id as `02 Site ID`,

    'School Leadership' as `03 Role Name`,

    concat(
        {{ current_school_year(var("local_timezone")) }},
        '-',
        {{ current_school_year(var("local_timezone")) }} + 1
    ) as `04 Academic Year`,

    1 as `05 Session Type ID`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_people__temp_staff") }}
