select *,
from
    {{
        source(
            "google_sheets", "src_google_sheets__google_forms__form_items_extension"
        )
    }}
