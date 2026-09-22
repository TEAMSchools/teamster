with
    per_round as (
        select
            academic_year,
            region,
            student_number,
            expected_test,
            expected_round_number,
            model_type,

            count(distinct pm_round_status) as n_pm_round_status,
            count(distinct round_benchmark_status) as n_round_benchmark_status,
            count(distinct round_trajectory_status) as n_round_trajectory_status,
            count(distinct aimline_round_category) as n_aimline_round_category,

        from {{ ref("rpt_tableau__dibels_dashboard") }}
        where model_type != 'BM'
        group by
            academic_year,
            region,
            student_number,
            expected_test,
            expected_round_number,
            model_type
    )

select *,
from per_round
where
    n_pm_round_status > 1
    or n_round_benchmark_status > 1
    or n_round_trajectory_status > 1
    or n_aimline_round_category > 1
