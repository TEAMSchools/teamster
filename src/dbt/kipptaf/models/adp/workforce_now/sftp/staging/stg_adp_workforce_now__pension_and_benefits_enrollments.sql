select * except (employee_number), cast(employee_number as int) as employee_number,
from
    {{
        source(
            "adp_workforce_now",
            "src_adp_workforce_now__pension_and_benefits_enrollments",
        )
    }}
