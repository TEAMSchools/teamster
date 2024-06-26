select
    academic_year,
    employee_number,
    etr_score,
    form_long_name as rubric_name,
    form_term as code,
    form_type,
    glows,
    grows,
    measurement_name,
    observation_id,
    observer_employee_number,
    overall_score as score,
    rn_submission,
    row_score_value as value_score,
    rubric_id,
    score_measurement_id,
    score_measurement_shortname,
    score_measurement_type,
    so_score,
    teacher_id,
    text_box,
    _dagster_partition_academic_year,
    _dagster_partition_term,

    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    'Coaching Tool: Coach ETR and Reflection' as `name`,

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
from
    {{
        source(
            "performance_management",
            "src_performance_management__observation_details",
        )
    }}
