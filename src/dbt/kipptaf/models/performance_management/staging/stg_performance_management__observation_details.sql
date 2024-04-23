select *,
from
    {{
        source(
            "performance_management",
            "src_performance_management__observation_details",
        )
    }}
