select
    assessment_id,
    contact_id,
    assessed_at,
    assessed_by,
    career_ready_level,
    active_search_level,
    internship_experience_level,
    network_level,
    coaching_focus,
    next_action,
    notes,

    concat('career_ready_', career_ready_level) as career_ready_rubric_key,
    concat('active_search_', active_search_level) as active_search_rubric_key,
    concat(
        'internship_experience_', internship_experience_level
    ) as internship_experience_rubric_key,
    concat('network_', network_level) as network_rubric_key,
from
    {{
        source(
            "google_appsheet",
            "src_google_appsheet__kfwd_career_conversations__assessments",
        )
    }}
