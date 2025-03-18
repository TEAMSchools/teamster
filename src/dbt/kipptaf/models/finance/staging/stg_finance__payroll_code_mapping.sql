select old_project_id_alt_nj, project_id, project_name,
from {{ source("finance", "src_finance__payroll_code_mapping") }}
