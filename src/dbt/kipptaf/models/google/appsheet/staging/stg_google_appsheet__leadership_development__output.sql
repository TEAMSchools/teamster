select *, cast(coalesce(edited_at, '1970-01-01') as timestamp) as edited_at_timestamp,
from
    {{
        source(
            "google_appsheet", "src_google_appsheet__leadership_development__output"
        )
    }}
