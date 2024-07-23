select
    employee_number,
    academic_year,
    form_type,
    observation_id,
    teacher_id,
    rubric_id,
    form_long_name as rubric_name,
    measurement_name,
    row_score_value as value_score,
    score_measurement_type,
    score_measurement_id,
    score_measurement_shortname,
    text_box,
    glows,
    grows,
    rn_submission,
    overall_score as score,
    overall_tier,
    etr_score,
    etr_tier,
    so_score,
    final_score,

    true as locked,
    'Teacher Performance Management' as observation_type,
    'PM' as observation_type_abbreviation,
    'Coaching Tool: Coach ETR and Reflection' as term_name,

    timestamp(observed_at) as observed_at,
    date(observed_at) as observed_at_date_local,

    coalesce(pm_term, form_term) as term_code,
    coalesce(so_tier.long_value, cast(so_tier.double_value as int)) as so_tier,
    coalesce(final_tier.long_value, cast(final_tier.double_value as int)) as final_tier,
    coalesce(
        observer_employee_number.long_value,
        cast(observer_employee_number.double_value as int)
    ) as observer_employee_number,

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
        form_term
        when 'PM1'
        then date(academic_year, 10, 1)
        when 'PM2'
        then date(academic_year + 1, 1, 1)
        when 'PM3'
        then date(academic_year + 1, 3, 1)
    end as eval_date,
from
    {{
        source(
            "performance_management",
            "src_performance_management__observation_details_archive",
        )
    }}
