select
    academic_year_int as academic_year,
    student_id as student_number,
    student_grade as grade_level,
    if(student_grade = 'K', 0, safe_cast(student_grade as int)) as grade_level_int,
    test_round as period,
    start_date,
    completion_date,

    subject,
    baseline_diagnostic_y_n,
    most_recent_diagnostic_ytd_y_n,
    rush_flag,
    overall_scale_score
    mid_on_grade_level_scale_score,
    placement_3_level,
    overall_relative_placement,
    overall_relative_placement_int,
    percent_progress_to_annual_typical_growth_percent,
    percent_progress_to_annual_stretch_growth_percent,
    projected_sublevel,
    projected_sublevel_number,
    projected_sublevel_typical,
    projected_sublevel_number_typical,
    projected_sublevel_stretch,
    projected_sublevel_number_stretch,

    mid_on_grade_level_scale_score
    - overall_scale_score as scale_pts_to_mid_on_grade_level,

    'Diagnostic' as assessment_type,

from {{ ref("base_iready__diagnostic_results") }}
where rn_subj_round = 1

union all

select
from {{ ref("model_name") }}
