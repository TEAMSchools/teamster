select
    project_id,
    project_name,

    cast(old_project_id_alt_nj as string) as old_project_id_alt_nj,
from {{ source("finance", "src_finance__payroll_code_mapping") }}
