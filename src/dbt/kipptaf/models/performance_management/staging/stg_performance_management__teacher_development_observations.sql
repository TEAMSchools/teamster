select
    observation_id,
    employee_number,
    observation_type,
    subject,
    observation_notes,
    growth_area,
    datetime as observed_at,
    observer_team,
    growth_notes,
    glow_area,
    glow_notes,
    TRIM(SPLIT(observer, ' - ')[OFFSET(0)]) AS observer_name,
from {{ source("google_appsheet", "src_teacher_development__observation_archive") }}
where observation_id is not null