select *,
from
    {{
        source(
            "adp_workforce_now",
            "src_adp_workforce_now__pension_and_benefits_enrollments",
        )
    }}
