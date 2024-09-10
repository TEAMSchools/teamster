select
    studentid.int_value as studentid,
    logtypeid.int_value as logtypeid,
    entry_date,
    `entry`,

    {{
        teamster_utils.date_to_fiscal_year(
            date_field="entry_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from {{ source("powerschool", "src_powerschool__log") }}
