select *, academic_year + 1 as fiscal_year,
from
    {{
        source(
            "performance_management",
            "src_performance_management__leadership_development_metrics",
        )
    }}
where not `disabled`
