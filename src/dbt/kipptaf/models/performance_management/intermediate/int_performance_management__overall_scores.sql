with
    final_score as (
        select employee_number, academic_year, avg(observation_score) as final_score,
        from {{ ref("int_performance_management__observation_details") }}
        where
            observation_type = 'PM'
            and academic_year = {{ var("current_academic_year") }}
            and code in ('PM2', 'PM3')
        group by employee_number, academic_year

    ),

    final_score_and_tier as (
        select
            employee_number,
            academic_year,
            final_score,

            case
                when final_score >= 3.495
                then 4
                when final_score >= 2.745
                then 3
                when final_score >= 1.745
                then 2
                when final_score < 1.75
                then 1
            end as final_tier,
        from final_score
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

    od.etr_tier,
    od.so_tier,
    od.overall_tier,
    od.eval_date,
from {{ ref("int_performance_management__observation_details") }} as od
left join
    final_score_and_tier as f
    on od.employee_number = f.employee_number
    and od.academic_year = f.academic_year
where
    od.observation_type = 'PM' and od.academic_year = {{ var("current_academic_year") }}

union all

select
    employee_number,
    observation_id,
    academic_year,
    code,
    etr_score,
    so_score,
    score as observation_score,

    null as final_score,
    null as final_tier,
    null as etr_tier,
    null as so_tier,
    null as overall_tier,

    eval_date,
from {{ ref("stg_performance_management__observation_details") }}
