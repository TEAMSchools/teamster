select
    obvs_micro_id as row_id,
    observation_id,
    employee_number,
    microgoal_id,
    esog as text_box,
    row_score,
    measurement_name,
    strand_name,
from
    {{
        source(
            "google_appsheet", "src_teacher_development__observation_details_archive"
        )
    }}
where esog is not null
