select
    account_id,
    college_name_nsc,
    college_state_nsc,
    college_code_nsc,
    meets_full_need,
    is_strong_oos_option,

    row_number() over (
        partition by account_id order by college_name_nsc desc
    ) as rn_account,
from {{ source("kippadb", "src_kippadb__nsc_crosswalk") }}
