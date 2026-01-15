select
    *,

    row_number() over (
        partition by account_id order by college_name_nsc desc
    ) as rn_account,
from {{ source("google_sheets", "src_google_sheets__kippadb__nsc_crosswalk") }}
