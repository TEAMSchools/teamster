/*add new measurement groups and observation types*/

select
    os.employee_number,
    os.academic_year,
    os.form_term,
    os.etr_score,
    os.so_score,
    os.overall_score,
    os.form_long_name,
    os.form_short_name,
    os.observation_id,
    os.rubric_id,
    'ETR' as observation_type

    ds.score_type,
    ds.observer_employee_number,
    sr.preferred_name_lastfirst,
    ds.observed_at,
    ds.measurement_name,
    ds.row_score_value,
from {{ ref("stg_performance_management__scores_overall_archive") }} as os
inner join
    {{ ref("stg_performance_management__scores_detail_archive") }} as ds
    on os.employee_number = ds.employee_number
    and os.academic_year = ds.academic_year
    and os.form_term = ds.form_term
left join {{ ref('base_people__staff_roster') }} as sr
on ds.observer_employee_number = sr.employee_number

/*union to 2023 static table*/