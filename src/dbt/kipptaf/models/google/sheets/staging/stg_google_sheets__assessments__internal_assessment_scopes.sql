select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__assessments__internal_assessment_scopes",
        )
    }}
