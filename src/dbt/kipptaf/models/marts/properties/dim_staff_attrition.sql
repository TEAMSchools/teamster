with
    attrition_effective_dates as (
        select date_day,
        from
            unnest(
                generate_date_array(
                    /* first date of the attrition snapshot*/
                    '2025-09-01',
                    date_add(
                        current_date('{{ var("local_timezone") }}'), interval 1 year
                    ),
                    interval 1 year
                )
            ) as date_day
    ),

    date_spine as (
        select
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.schoolid,
            cw.academic_year,
            case
                when aed.date_day > cw.week_end_sunday
                then cw.academic_year - 1
                else cw.academic_year
            end as attrition_year,
        from {{ ref("int_powerschool__calendar_week") }} as cw
        left join
            attrition_effective_dates as aed
            on cw.academic_year = extract(year from aed.date_day)
        where cw.academic_year >= 2025
    )

select
    sad.employee_number,
    sad.business_unit_home_name as entity
    sad.home_work_location_name as location,
    sad.home_work_location_grade_band as grade_band
    sad.department_home_name as department,
    sad.job_title,
    sad.report_to_preferred_name_lastfirst as manager,
    sad.original_hire_date as worker_original_hire_date,
    sad.assignment_status,
    sad.termination_date as worker_termination_date,
    sad.year_at_kipp,
    sad.race_ethnicity_reporting,
    sad.gender_identity,
    ds.academic_year,
    ds.week_start_monday,
    ds.week_end_sunday,
    if(
        sad.job_title in (
            'Teacher',
            'Teacher in Residence',
            'ESE Teacher',
            'Learning Specialist',
            'Teacher ESL',
            'Teacher in Residence ESL'
        ),
        true,
        false
    ) as is_teacher
    case
        when sad.termination_date is null
        then sad.is_attrition
        when sad.termination_date < ds.week_end_sunday
        then sad.is_attrition
        else 0
    end as is_attrition,
from {{ ref("rpt_tableau__staff_attrition_details") }} as sad
/* change to {{ ref("int_people__staff_attrition_details") }}  when it's ready*/
inner join
    date_spine as ds
    on sad.academic_year = ds.attrition_year
    and (
        (sad.ps_school_id = ds.schoolid)
        or if(sad.ps_school_id = 0, 133570965, sad.ps_school_id) = ds.schoolid
        or coalesce(sad.ps_school_id, 133570965) = ds.schoolid
    )
