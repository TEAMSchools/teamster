with
    dso as (
        select
            home_work_location_name,
            max(employee_number) as dso_employee_number,
        from {{ ref("base_people__staff_roster") }}
        where
            job_title
            in ('Director School Operations', 'Director Campus Operations', 'Director')
            and assignment_status != 'Terminated'
            and department_home_name = 'Operations'
        group by home_work_location_name
    ),
    mdso as (
        select employee_number, max(report_to_employee_number) as mdso_employee_number,
        from {{ ref("base_people__staff_roster") }}
        where
            job_title
            in ('Director School Operations', 'Director Campus Operations', 'Director')
            and assignment_status != 'Terminated'
        group by employee_number
    ),
    sl as (
        select home_work_location_name, max(employee_number) as sl_employee_number,
        from {{ ref("base_people__staff_roster") }}
        where
            job_title in ('School Leader', 'School Leader in Residence')
            and assignment_status != 'Terminated'
        group by home_work_location_name
    ),
    hos as (
        select employee_number, max(report_to_employee_number) as hos_employee_number,
        from {{ ref("base_people__staff_roster") }}
        where
            job_title in ('School Leader', 'School Leader in Residence')
            and assignment_status != 'Terminated'
        group by employee_number
    )




select
    *
from {{ ref("rpt_gsheets__stipends_app_roster") }} as sr
left join dso as dso on sr.home_work_location_name = dso.home_work_location_name
left join mdso as mdso on dso.dso_employee_number = mdso.employee_number
left join sl as sl on sr.home_work_location_name = sl.home_work_location_name
left join hos as hos on sl.sl_employee_number = hos.employee_number
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
