/* KNJ specific departments = all CMO schools */
select
    -- noqa: disable=RF05
    sr.powerschool_teacher_number as `01 Local User ID`,

    sch.school_number as `02 Site ID`,

    'School Leadership' as `03 Role Name`,
    concat(
        {{ var("current_academic_year") }}, '-', {{ var("current_fiscal_year") }}
    ) as `04 Academic Year`,
    1 as `05 Session Type ID`,
from {{ ref("base_people__staff_roster") }} as sr
inner join
    {{ ref("stg_powerschool__schools") }} as sch on sch.state_excludefromreporting = 0
where
    sr.assignment_status != 'Terminated'
    and sr.department_home_name in ('Teaching and Learning', 'Data', 'Executive')
    and sr.business_unit_home_name = 'KIPP TEAM and Family Schools Inc.'

union all

/* Campus-based staff = all schools at campus */
select
    sr.powerschool_teacher_number as `01 Local User ID`,

    cc.powerschool_school_id as `02 Site ID`,

    'School Leadership' as `03 Role Name`,
    concat(
        {{ var("current_academic_year") }}, '-', {{ var("current_fiscal_year") }}
    ) as `04 Academic Year`,
    1 as `05 Session Type ID`,
from {{ ref("base_people__staff_roster") }} as sr
inner join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.name
    and not cc.is_pathways
where
    sr.assignment_status != 'Terminated'
    and sr.department_home_name not in ('Teaching and Learning', 'Data', 'Executive')
    and sr.home_work_location_is_campus

union all

/* School-based staff = only respective school */
select
    powerschool_teacher_number as `01 Local User ID`,
    home_work_location_powerschool_school_id as `02 Site ID`,

    'School Leadership' as `03 Role Name`,
    concat(
        {{ var("current_academic_year") }}, '-', {{ var("current_fiscal_year") }}
    ) as `04 Academic Year`,
    1 as `05 Session Type ID`,
from {{ ref("base_people__staff_roster") }}
where
    assignment_status != 'Terminated'
    and department_home_name not in ('Teaching and Learning', 'Data', 'Executive')
    and not home_work_location_is_campus
