select
    *,
    row_number() over (
        partition by account_id order by college_name_nsc desc
    ) as rn_account,
from {{ source("kippadb", "src_kippadb__nsc_crosswalk") }}
