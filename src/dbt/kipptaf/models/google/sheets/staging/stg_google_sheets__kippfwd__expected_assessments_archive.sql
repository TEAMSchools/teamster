select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__kippfwd__expected_assessments_archive",
        )
    }}
