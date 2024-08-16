select
    observation_id,
    employee_number,
    observation_type,
    `subject`,
    observation_notes,
    growth_area,
    observer_team,
    growth_notes,
    glow_area,
    glow_notes,

    timestamp(`datetime`, '{{ var("local_timezone") }}') as observed_at,

    trim(split(observer, '-')[0]) as observer_name,
from {{ source("google_appsheet", "src_teacher_development__observation_archive") }}
where observation_id is not null
