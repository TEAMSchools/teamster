with
    overall_scores as (
        select
            employee_number,
            academic_year,
            pm_term as code,
            etr_score,
            so_score,
            overall_score,
            etr_tier,
            so_tier,
            overall_tier as tier
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
            code,
            null as etr_score,
            null as so_score,
            overall_score,
            null as etr_tier,
            null as so_tier,
            tier,
        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where type = 'PM' and overall_score is not null
    ),

    detail_scores as (
        select
            subject_employee_number as employee_number,
            academic_year,
            pm_term as code,
            score_type,
            observer_employee_number,
            NULL AS observer_name,
            observed_at,
            measurement_name,
            answer,
            score_value as row_score_value,
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
            employee_number,
            academic_year,
            code,
            NULL AS score_type,
            NULL AS observer_employee_number,
            observer_name,
            observed_at,
            measurement_name,
            NULL as answer,
            row_score_value,
            NULL AS score_value_weighted,

        from {{ ref("rpt_tableau__schoolmint_grow_observation_details") }}
        where type = 'PM' and overall_score is not null
    )

select *
from
    detail_scores as ds
left join
    overall_scores as os
    on ds.employee_number = os.employee_number
    and ds.academic_year = os.academic_year
    and ds.code= os.code
