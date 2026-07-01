select *,
from
    {{
        source(
            "google_sheets",
            "src_google_sheets__people__cube_access_individual_exceptions",
        )
    }}
where employee_number is not null
