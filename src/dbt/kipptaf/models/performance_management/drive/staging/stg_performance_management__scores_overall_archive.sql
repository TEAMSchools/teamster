select
    * except (pm_term),

    pm_term as form_term,

    'Coaching Tool: Coach ETR and Reflection' as form_long_name,

    concat(academic_year, pm_term) as rubric_id,
    concat(academic_year, pm_term, employee_number) as observation_id,
    concat(pm_term, ' (Coach)') as form_short_name,

    case
        when pm_term = 'PM1'
        then date(academic_year, 10, 1)
        when pm_term = 'PM2'
        then date(academic_year + 1, 1, 1)
        when pm_term = 'PM3'
        then date(academic_year + 1, 3, 1)
        when pm_term = 'PM4'
        then date(academic_year + 1, 5, 15)
    end as eval_date,
from
    {{
        source(
            "performance_management",
            "src_performance_management__scores_overall_archive",
        )
    }}
