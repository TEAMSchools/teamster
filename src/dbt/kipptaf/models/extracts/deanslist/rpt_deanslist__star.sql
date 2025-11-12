with
    star as (
        select
            student_display_id as student_number,
            academic_year,
            screening_period_window_name as test_round,
            star_discipline as discipline,
            unified_score,

            'Benchmark' as score_type,

            if(
                grade_level = 0,
                district_benchmark_category_level,
                state_benchmark_category_level
            ) as state_benchmark_category_level,

            if(
                grade_level = 0,
                district_benchmark_category_name,
                state_benchmark_category_name
            ) as state_benchmark_category_name,

            if(
                grade_level = 0,
                district_benchmark_proficient,
                state_benchmark_proficient
            ) as state_benchmark_proficient,
        from {{ ref("stg_renlearn__star") }}
        where rn_subject_round = 1
    )

select
    *, concat(state_benchmark_category_name, ' (', unified_score, ')') as score_display,
from star
