select
    source,
    student_number,
    academic_year,
    assessment_id,
    title,
    scope,
    subject_area,
    term_administered,
    is_internal_assessment,
    is_replacement,
    response_type,
    response_type_code,
    response_type_description,

    if(
        count(*) = 1,
        any_value(percent_correct),
        safe_divide(sum(points), sum(points_possible)) * 100
    ) as percent_correct,
    if(count(*) = 1, any_value(performance_band_label), null) as performance_band_label,
from {{ ref("int_assessments__response_rollup") }}
where response_type = 'standard'
group by
    source,
    student_number,
    academic_year,
    assessment_id,
    title,
    scope,
    subject_area,
    term_administered,
    is_internal_assessment,
    is_replacement,
    response_type,
    response_type_code,
    response_type_description
