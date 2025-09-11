with
    metric_union as (
        select
            academic_year,
            employee_number,
            school_id as schoolid,
            week_start_monday as term,
            'Outstanding Teammates are Everything' as layer,
            'Microgoals' as indicator,

            null as numerator,
            null as denominator,
            if(microgoals_assigned >= 1, 1, 0) as metric_value,
        from {{ ref("int_topline__microgoals_assigned_weekly") }}

        union all

        select
            academic_year,
            employee_number,
            ps_school_id as schoolid,
            week_start_monday as term,
            'Outstanding Teammates are Everything' as layer,
            'Retention' as indicator,

            null as numerator,
            null as denominator,
            is_retention as metric_value,
        from {{ ref("int_topline__staff_retention") }}
    )

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

    mu.layer,
    mu.indicator,
    mu.numerator,
    mu.denominator,
    mu.metric_value,
from {{ ref("int_topline__people_spine") }} as ss
left join
    metric_union as mu
    on ss.employee_number = mu.employee_number
    and ss.home_work_location_powerschool_school_id = mu.schoolid
    and ss.academic_year = mu.academic_year
    and ss.week_start_monday = mu.term
where ss.academic_year >= {{ var("current_academic_year") - 1 }}
