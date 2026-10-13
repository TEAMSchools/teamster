select
    student_number,
    assessment_year as academic_year,
    academic_year as academic_year_int,
    administration_period as test_round,
    assessment_name as test_type,
    discipline as `subject`,
    raw_subject as test_name,
    scale_score,
    performance_level_label as proficiency_level,

    if(is_proficient, 1, 0) as is_proficient,

    concat(performance_level_label, ' (', scale_score, ')') as score_display,

    row_number() over (
        partition by student_number, raw_subject
        order by assessment_year asc, administration_period asc
    ) as test_index,
from {{ ref("int_assessments__state_nj_scores") }}
