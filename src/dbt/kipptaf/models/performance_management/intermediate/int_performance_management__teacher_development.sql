with
    archive_average_scores as (
        select observation_id, avg(row_score) as average_row_score,
        from
            {{
                ref(
                    "stg_performance_management__teacher_development_observation_details"
                )
            }}
        group by observation_id
    )

select
    o.employee_number,
    o.observation_id,
    o.academic_year,
    o.observed_at,
    o.subject as observation_subject,
    o.growth_area,
    o.glow_area,
    o.observer_team,
    o.observer_name,
    o.observation_type_abbreviation,

    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,

    av.average_row_score as observation_score,

    sr.employee_number as observer_employee_number,

    'Teacher Development' as observation_type,

    concat('Teacher Development: ', o.observation_type) as rubric_name,
from {{ ref("stg_performance_management__teacher_development_observations") }} as o
left join
    {{ ref("stg_performance_management__teacher_development_observation_details") }}
    as od
    on o.observation_id = od.observation_id
left join archive_average_scores as av on o.observation_id = av.observation_id
left join
    {{ ref("base_people__staff_roster") }} as sr
    on o.observer_name = sr.preferred_name_lastfirst
where od.row_score is not null
