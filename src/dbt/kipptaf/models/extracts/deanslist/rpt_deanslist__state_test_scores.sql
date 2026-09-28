select
    localstudentidentifier as student_number,
    assessmentyear as academic_year,
    academic_year as academic_year_int,
    administration_period as test_round,
    assessment_name as test_type,
    discipline as `subject`,
    `subject` as test_name,
    testscalescore as scale_score,
    testperformancelevel_text as proficiency_level,

    if(is_proficient, 1, 0) as is_proficient,

    concat(testperformancelevel_text, ' (', testscalescore, ')') as score_display,

    row_number() over (
        partition by localstudentidentifier, `subject`
        order by assessmentyear asc, administration_period asc
    ) as test_index,
from {{ ref("int_pearson__all_assessments") }}
