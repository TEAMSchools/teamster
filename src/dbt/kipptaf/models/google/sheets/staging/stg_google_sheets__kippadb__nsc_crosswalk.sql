select
    account_id,
    college_name_nsc,
    college_state_nsc,
    college_code_nsc,
    meets_full_need,
    is_strong_oos_option,
    nces_id,
    overgrad_urm_grad_rate,

    row_number() over (
        partition by account_id order by college_name_nsc desc
    ) as rn_account,
    row_number() over (
        partition by college_code_nsc order by college_name_nsc desc
    ) as rn_college_code_nsc,
from {{ source("google_sheets", "src_google_sheets__kippadb__nsc_crosswalk") }}
