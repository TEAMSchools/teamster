select
    2024 as academic_year,

    region,
    grade_level,
    period,
    pm_round,
    start_date,
    end_date,
    goal,
    measure_level_code,
    measure_standard,

    bm_goal,

from
    {{ source("google_sheets", "src_google_sheets__dibels_pm_expectations") }}
    unpivot (bm_goal for benchmark_goal in (moy_benchmark, eoy_benchmark))
