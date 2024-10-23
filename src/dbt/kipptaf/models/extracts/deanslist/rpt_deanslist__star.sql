select
    student_display_id as student_number,
    academic_year,
    screening_period_window_name as test_round,
    star_discipline as discipline,
    state_benchmark_category_level,
    state_benchmark_category_name,
    state_benchmark_proficient,
    unified_score,

    'Benchmark' as score_type,

    concat(state_benchmark_category_name, ' (', unified_score, ')') as score_display,
from {{ ref("int_renlearn__star_rollup") }}
where rn_subj_round = 1
