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
    sad.ps_school_id,
    ds.academic_year,
    ds.week_start_monday,
    ds.week_end_sunday,
    case
        when sad.termination_date is null
        then 1 - sad.is_attrition
        when sad.termination_date < ds.week_end_sunday
        then 1 - sad.is_attrition
        else 1
    end as is_retention,
from {{ ref("int_people__staff_attrition_details") }} as sad
inner join
    date_spine as ds
    on sad.academic_year = ds.attrition_year
    and (
        (sad.ps_school_id = ds.schoolid)
        or if(sad.ps_school_id = 0, 133570965, sad.ps_school_id) = ds.schoolid
        or coalesce(sad.ps_school_id, 133570965) = ds.schoolid
    )
