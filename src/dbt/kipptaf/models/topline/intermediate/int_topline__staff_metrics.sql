select
    ss.employee_number,
    ss.powerschool_teacher_number,
    ss.home_business_unit_name,
    ss.home_work_location_powerschool_school_id,
    ss.home_work_location_name,
    ss.home_department_name,
    ss.job_title,
    ss.assignment_status,
    ss.reports_to_user_principal_name,
    ss.academic_year,
    ss.week_start_monday,
    ss.week_end_sunday,
    ss.is_current_week,

    'Outstanding Teammates' as layer,
    "Microgoals" as indicator,

    ma.week_start_monday as term,

    null as numerator,
    null as denominator,

    if(ma.microgoals_assigned >= 1, 1, 0) as metric_value,
from {{ ref("int_topline__people_spine") }} as ss
left join
    {{ ref("int_topline__microgoals_assigned_weekly") }} as ma
    on ss.employee_number = ma.employee_number
    and ss.home_work_location_powerschool_school_id = ma.school_id
    and ss.academic_year = ma.academic_year
    and ss.week_start_monday = ma.week_start_monday
where
    ss.academic_year >= {{ var("current_academic_year") - 1 }}
    and ss.assignment_status = 'Active'

union all

select
    ss.employee_number,
    ss.powerschool_teacher_number,
    ss.home_business_unit_name,
    ss.home_work_location_powerschool_school_id,
    ss.home_work_location_name,
    ss.home_department_name,
    ss.job_title,
    ss.assignment_status,
    ss.reports_to_user_principal_name,
    ss.academic_year,
    ss.week_start_monday,
    ss.week_end_sunday,
    ss.is_current_week,

    'Outstanding Teammates' as layer,
    "Staff Retention" as indicator,

    sr.week_start_monday as term,

    null as numerator,
    null as denominator,

    sr.is_retention as metric_value,
from {{ ref("int_topline__people_spine") }} as ss
left join
    {{ ref("int_topline__staff_retention") }} as sr
    on ss.employee_number = sr.employee_number
    and ss.home_work_location_powerschool_school_id = sr.ps_school_id
    and ss.academic_year = sr.academic_year
    and ss.week_start_monday = sr.week_start_monday
where ss.academic_year >= {{ var("current_academic_year") - 1 }}
