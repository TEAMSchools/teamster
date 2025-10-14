select *,
from
    {{ source("google_sheets", "src_google_sheets__coupa__intacct_department_lookup") }}
