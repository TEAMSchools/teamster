select *, from {{ source("finance", "src_finance__payroll_code_mapping") }}
