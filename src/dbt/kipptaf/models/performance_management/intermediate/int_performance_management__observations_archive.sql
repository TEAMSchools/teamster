with
    observer as (
        select
            observation_id,
            if(
                academic_year < 2023,
                'Multiple',
                cast(observer_employee_number as string)
            ) as observer_employee_number,
        from {{ ref("stg_performance_management__observation_details_archive") }}
    )

select
    ods.employee_number,
    ods.observation_id,
    ods.academic_year,
    ods.term_code,
    ods.term_name,
    ods.rubric_name,
    ods.observation_type,
    ods.observation_type_abbreviation,
    ods.eval_date,
    ods.score,
    ods.overall_tier,
    ods.etr_score,
    ods.etr_tier,
    ods.so_score,
    ods.so_tier,
    ods.final_score,
    ods.final_tier,
    ods.glows,
    ods.grows,
    ods.locked,
    o.observer_employee_number,

    max(ods.observed_at) as observed_at,
    max(ods.observed_at_date_local) as observed_at_date_local,
from {{ ref("stg_performance_management__observation_details_archive") }} as ods
left join observer as o on ods.observation_id = o.observation_id
group by
    employee_number,
    observation_id,
    academic_year,
    term_code,
    term_name,
    rubric_name,
    observation_type,
    observation_type_abbreviation,
    eval_date,
    score,
    overall_tier,
    etr_score,
    etr_tier,
    so_score,
    so_tier,
    final_score,
    final_tier,
    glows,
    grows,
    locked,
    observer_employee_number
