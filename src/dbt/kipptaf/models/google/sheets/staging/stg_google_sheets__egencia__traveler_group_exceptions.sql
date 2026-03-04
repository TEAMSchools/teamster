select *,
from
    {{
        source(
            "google_sheets", "src_google_sheets__egencia__traveler_group_exceptions"
        )
    }}
