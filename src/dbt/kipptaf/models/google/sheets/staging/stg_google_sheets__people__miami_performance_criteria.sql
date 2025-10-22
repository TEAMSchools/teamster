select * except (`group`), `group` as criteria_group,
from
    {{
        source(
            "google_sheets", "src_google_sheets__people__miami_performance_criteria"
        )
    }}
