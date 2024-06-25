with
    final_score_and_tier as (
        select
            employee_number,
            academic_year,
            avg(observation_score) as final_score,
            case
                when avg(observation_score) >= 3.495
                then 4
                when avg(observation_score) >= 2.745
                then 3
                when avg(observation_score) >= 1.745
                then 2
                when avg(observation_score) < 1.75
                then 1
            end as final_tier,
        from {{ ref("int_performance_management__observation_details") }}
        where
            observation_type = 'PM'
            and code in ('PM2', 'PM3')
            and observation_score is not null
            and academic_year = {{ var("current_academic_year") }}
        group by employee_number, academic_year

    )

select
    od.employee_number,
    od.observation_id,
    od.academic_year,
    od.code,
    od.etr_score,
    od.so_score,
    od.observation_score,
    f.final_score,
    f.final_tier,
    case
        when od.etr_score >= 3.495
        then 4
        when od.etr_score >= 2.745
        then 3
        when od.etr_score >= 1.745
        then 2
        when od.etr_score < 1.75
        then 1
    end as etr_tier,
    case
        when od.so_score >= 3.495
        then 4
        when od.so_score >= 2.945
        then 3
        when od.so_score >= 1.945
        then 2
        when od.so_score < 1.95
        then 1
    end as so_tier,
    case
        when od.observation_score >= 3.495
        then 4
        when od.observation_score >= 2.745
        then 3
        when od.observation_score >= 1.745
        then 2
        when od.observation_score < 1.75
        then 1
    end as overall_tier,

    case
        when code = 'PM1'
        then date(od.academic_year, 10, 1)
        when code = 'PM2'
        then date(od.academic_year + 1, 1, 1)
        when code = 'PM3'
        then date(od.academic_year + 1, 3, 1)
    end as eval_date,
from {{ ref("int_performance_management__observation_details") }} as od
join
    final_score_and_tier as f
    on od.employee_number = f.employee_number
    and od.academic_year = f.academic_year
where observation_type = 'PM' and od.academic_year = {{ var("current_academic_year") }}
group by
    od.employee_number,
    od.observation_id,
    od.academic_year,
    od.code,
    od.etr_score,
    od.so_score,
    od.observation_score,
    f.final_score,
    f.final_tier

union all

select
    employee_number,
    observation_id,
    academic_year,
    form_term as code,
    etr_score,
    so_score,
    overall_score as observation_score,
    null as final_score,
    null as final_tier,
    null as etr_tier,
    null as so_tier,
    null as overall_tier,
    case
        when form_term = 'PM1'
        then date(academic_year, 10, 1)
        when form_term = 'PM2'
        then date(academic_year + 1, 1, 1)
        when form_term = 'PM3'
        then date(academic_year + 1, 3, 1)
    end as eval_date,
from {{ ref("stg_performance_management__observation_details") }}
group by
    employee_number,
    observation_id,
    academic_year,
    form_term,
    etr_score,
    so_score,
    overall_score
