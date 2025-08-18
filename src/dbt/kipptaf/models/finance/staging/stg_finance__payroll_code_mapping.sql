select
    project_name,

    cast(project_id as string) as project_id,
    cast(old_project_id_alt_nj as string) as old_project_id_alt_nj,
from {{ source("finance", "src_finance__payroll_code_mapping") }}
