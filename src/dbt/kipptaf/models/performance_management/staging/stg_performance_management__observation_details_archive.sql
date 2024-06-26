select
    employee_number,
    academic_year,
    form_term as term_code,
    form_type,
    observation_id,
    teacher_id,
    rubric_id,
    form_long_name as rubric_name,
    observer_employee_number,
    measurement_name,
    row_score_value as value_score,
    score_measurement_type,
    score_measurement_id,
    score_measurement_shortname,
    overall_score as score,
    etr_score,
    so_score,
    text_box,
    glows,
    grows,
    rn_submission,

    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    'Coaching Tool: Coach ETR and Reflection' as term_name,

    timestamp(observed_at) as observed_at,
    date(observed_at) as observed_at_date_local,

    case
        when score_measurement_type = 'etr'
        then 'Excellent Teaching Rubric'
        when score_measurement_type = 's&o'
        then 'Self & Others: Manager Feedback'
        else 'Comments'
    end as measurement_group_name,
    case
        when score_measurement_type = 'etr'
        then etr_score
        when score_measurement_type = 's&o'
        then so_score
    end as score_averaged_by_strand,
    case
        when form_term = 'PM1'
        then date(academic_year, 10, 1)
        when form_term = 'PM2'
        then date(academic_year + 1, 1, 1)
        when form_term = 'PM3'
        then date(academic_year + 1, 3, 1)
    end as eval_date,
    case
        when etr_score >= 3.495
        then 4
        when etr_score >= 2.745
        then 3
        when etr_score >= 1.745
        then 2
        when etr_score < 1.75
        then 1
    end as etr_tier,
    case
        when so_score >= 3.495
        then 4
        when so_score >= 2.945
        then 3
        when so_score >= 1.945
        then 2
        when so_score < 1.95
        then 1
    end as so_tier,
    case
        when overall_score >= 3.495
        then 4
        when overall_score >= 2.745
        then 3
        when overall_score >= 1.745
        then 2
        when overall_score < 1.75
        then 1
    end as overall_tier,
from
    {{
        source(
            "performance_management",
            "src_performance_management__observation_details",
        )
    }}
