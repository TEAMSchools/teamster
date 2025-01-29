select
    student_display_id as student_number,
    academic_year,
    screening_period_window_name as test_round,
    star_discipline as discipline,
    unified_score,

    if(
        grade_level = 0,
        district_benchmark_category_level,
        state_benchmark_category_level
    ) as state_benchmark_category_level,
    if(
        grade_level = 0, district_benchmark_category_name, state_benchmark_category_name
    ) as state_benchmark_category_name,
    if(
        grade_level = 0, district_benchmark_proficient, state_benchmark_proficient
    ) as state_benchmark_proficient,

    'Benchmark' as score_type,

    concat(
        if(
            grade_level = 0,
            district_benchmark_category_name,
            state_benchmark_category_name
        ),
        ' (',
        unified_score,
        ')'
    ) as score_display,
from {{ ref("int_renlearn__star_rollup") }}
where rn_subj_round = 1
