select
    school_id,
    region as entity,
    `type` as term_type,
    code as term_code,
    `name` as term_name,
    cast(`start_date` as timestamp) as term_start_date,
    cast(end_date as timestamp) as term_end_date,
    academic_year,
    fiscal_year,
    powerschool_year_id,
    powerschool_term_id,
    grade_band,
    cast(lockbox_date as timestamp) as lockbox_date,
    is_current,
    city,

    {{
        dbt_utils.generate_surrogate_key(
            ["type", "code", "name", "start_date", "region", "school_id"]
        )
    }} as terms_key,
from {{ ref("stg_google_sheets__reporting__terms") }}
