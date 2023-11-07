with
    overall_scores as (
        select
            employee_number,
            academic_year,
            pm_term,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier
        from
            {{
                source(
                    "performance_management",
                    "src_performance_management__scores_overall_archive",
                )
            }}

        union distinct

        select
            employee_number,
            academic_year,
            code as pm_term,
            null as etr_score,
            null as so_score,
            overall_score,
            null as etr_tier,
            null as so_tier,
            tier as overall_tier
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where type = 'PM' and overall_score is not null
    )

detail_scores as (
select
subject_employee_number,
academic_year,
pm_term,
score_type,
observer_employee_number,
observed_at,
measurement_name,
answer,
score_value,
score_value_weighted,
from
    {{
        source(
            "performance_management",
            "src_performance_management__scores_detail_archive",
        )
    }}

union all

select
subject_employee_number,
academic_year,
pm_term,
score_type,
observer_employee_number,
observed_at,
measurement_name,
answer,
score_value,
score_value_weighted,

)

select *
from
    {{
        source(
            "performance_management",
            "src_performance_management__scores_detail_archive",
        )
    }} as sda
left join
    overall_scores as os
    on sda.subject_employee_number = os.employee_number
    and sda.academic_year = os.academic_year
    and sda.pm_term = os.pm_term
