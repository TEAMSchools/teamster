with
    observation_details as (
        select
            form_type,
            observation_id,
            teacher_id,
            rubric_id,
            form_long_name as rubric_name,
            measurement_name,
            score_measurement_type,
            score_measurement_id,
            score_measurement_shortname,
            text_box,
            glows,
            grows,
            form_term,

            true as locked,
            'Teacher Performance Management' as observation_type,
            'PM' as observation_type_abbreviation,
            'Coaching Tool: Coach ETR and Reflection' as term_name,

            cast(employee_number as int) as employee_number,
            cast(academic_year as int) as academic_year,
            cast(so_tier as int) as so_tier,
            cast(final_tier as int) as final_tier,
            cast(observer_employee_number as int) as observer_employee_number,
            cast(rn_submission as int) as rn_submission,

            cast(etr_score as float64) as etr_score,
            cast(etr_tier as float64) as etr_tier,
            cast(final_score as float64) as final_score,
            cast(overall_tier as float64) as overall_tier,
            cast(so_score as float64) as so_score,
            cast(overall_score as float64) as score,
            cast(row_score_value as float64) as value_score,

            coalesce(pm_term, form_term) as term_code,

            coalesce(
                safe_cast(observed_at as timestamp),
                cast(parse_date('%m/%d/%Y', observed_at) as timestamp)
            ) as observed_at,

            case
                when score_measurement_type = 'etr'
                then 'Excellent Teaching Rubric'
                when score_measurement_type = 's&o'
                then 'Self & Others: Manager Feedback'
                else 'Comments'
            end as measurement_group_name,
        from
            {{
                source(
                    "performance_management",
                    "src_performance_management__observation_details_archive",
                )
            }}
    )

select
    *,

    date(observed_at, '{{ var("local_timezone") }}') as observed_at_date_local,

    case
        form_term
        when 'PM1'
        then date(academic_year, 10, 1)
        when 'PM2'
        then date(academic_year + 1, 1, 1)
        when 'PM3'
        then date(academic_year + 1, 3, 1)
    end as eval_date,
from observation_details
