select * except (employee_number), safe_cast(employee_number as int) as employee_number,
from
    {{
        source(
            "google_appsheet",
            "src_google_appsheet__leadership_development__active_users",
        )
    }}
