select
    {{ dbt_utils.generate_surrogate_key(["o.observation_id"]) }}
    as staff_observation_key,

    if(
        o.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["o.employee_number"]) }},
        cast(null as string)
    ) as teacher_staff_key,

    if(
        o.observer_employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["o.observer_employee_number"]) }},
        cast(null as string)
    ) as observer_staff_key,

    gro.location_key,

    o.term_key,

    o.staff_observation_type_key,

    o.staff_observation_rubric_key,

    o.academic_year,
    o.observation_score as score,
    o.overall_tier as overall_rating,
    o.observation_notes as notes,

    o.observed_at as observed_date_key,
    o.observed_at_timestamp as observed_timestamp,
    o.glows as positive_feedback,
    o.grows as growth_areas,
    o.locked as is_locked,
from {{ ref("int_performance_management__observations") }} as o
left join
    {{ ref("int_schoolmint_grow__observations") }} as gro
    on o.observation_id = gro.observation_id
