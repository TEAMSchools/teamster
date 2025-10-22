select *,
from
    {{
        source(
            "google_sheets", "src_google_sheets__assessments__qbls_power_standards"
        )
    }}
