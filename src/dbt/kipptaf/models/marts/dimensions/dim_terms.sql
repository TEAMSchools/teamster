select
    {{
        dbt_utils.generate_surrogate_key(
            ["type", "code", "name", "start_date", "region", "school_id"]
        )
    }} as term_key,

    `type` as term_type,
    code as term_code,
    `name` as term_name,
    `start_date` as term_start_date,
    end_date as term_end_date,
    academic_year,
    fiscal_year,
    region,
    school_id,
    grade_band,
    lockbox_date as data_freeze_date,
    is_current,
from {{ ref("stg_google_sheets__reporting__terms") }}
