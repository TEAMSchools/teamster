select
    * except (
        most_recent_completion_date,
        most_recent_diagnostic_gain,
        most_recent_lexile_measure,
        most_recent_lexile_range,
        most_recent_overall_placement,
        most_recent_overall_relative_placement,
        most_recent_overall_scale_score,
        most_recent_rush_flag
    ),

    max(most_recent_overall_scale_score) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_overall_scale_score,

    max(most_recent_overall_relative_placement) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_overall_relative_placement,

    max(most_recent_overall_placement) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_overall_placement,

    max(most_recent_diagnostic_gain) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_diagnostic_gain,

    max(most_recent_lexile_measure) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_lexile_measure,

    max(most_recent_lexile_range) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_lexile_range,

    max(most_recent_rush_flag) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_rush_flag,

    max(most_recent_completion_date) over (
        partition by student_id, academic_year, `subject`
    ) as most_recent_completion_date,

    row_number() over (
        partition by student_id, academic_year, `subject`
        order by completion_date desc, rn_subj_day asc
    ) as rn_subj_year,
from {{ ref("stg_iready__diagnostic_results") }}
