-- depends_on: {{ ref("stg_google_appsheet__kfwd_career_conversations__assessments") }}
select assessment_id, assessed_at, assessed_by,
from
    {{
        source(
            "google_appsheet",
            "src_google_appsheet__kfwd_career_conversations__assessments",
        )
    }}
where contact_id is null
