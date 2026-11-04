select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__kippfwd__practice_scale_score_conversion",
        )
    }}
