select
    Account_ID,
    College_Name_NSC,
    College_State_NSC,
    College_Code_NSC,
    Meets_Full_Need,
    Is_Strong_OOS_Option,
    NCES_ID,
    Overgrad_URM_Grad_Rate,

    row_number() over (
        partition by account_id order by college_name_nsc desc
    ) as rn_account,
    row_number() over (
        partition by college_code_nsc order by college_name_nsc desc
    ) as rn_college_code_nsc,
from {{ source("google_sheets", "src_google_sheets__kippadb__nsc_crosswalk") }}
