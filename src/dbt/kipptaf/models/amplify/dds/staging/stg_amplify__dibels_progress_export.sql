select
    student_id,
    measure,
    score,

    _dagster_partition_fiscal_year - 1 as academic_year,

    parse_date('%m/%d/%Y', assessment_dates) as assessment_dates,
from {{ source("amplify", "src_amplify__dibels_progress_export") }}
