select
    region,
    school_level,
    audit_category,
    audit_flag_name,
    grade_level,
    code,
    cte_grouping,
    code_type,
from {{ source("reporting", "src_reporting__gradebook_flags") }}
