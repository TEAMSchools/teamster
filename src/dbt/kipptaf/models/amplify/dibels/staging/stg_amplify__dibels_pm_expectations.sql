select
    *,

    {{
        teamster_utils.date_to_fiscal_year(
            date_field="start_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from {{ source("amplify", "src_amplify__dibels_pm_expectations") }}
