select
    subject_area,
    tier_update_method,
    tier_change_reason,
    tier_change_reason_notes,
    district,

    _dagster_partition_fiscal_year as source_fiscal_year,

    safe_cast(tier_update_id as int64) as tier_update_id,
    safe_cast(student_number as int64) as student_number,
    safe_cast(school_id as int64) as school_id,
    safe_cast(tier_level as int64) as tier_level,
    safe_cast(tier_update_date as date) as tier_update_date,
    safe_cast(last_evaluation_date as date) as last_evaluation_date,
from {{ source("branchingminds", "src_branchingminds__current_student_tier_levels") }}
