select
    project_name,

    cast(project_id as string) as project_id,
    cast(old_project_id_alt_nj as string) as old_project_id_alt_nj,
from {{ source("google_sheets", "src_google_sheets__finance__payroll_code_mapping") }}
