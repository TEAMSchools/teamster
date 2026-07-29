select
    gender,
    photolastupdated,
    pscore_legal_first_name,
    pscore_legal_gender,
    pscore_legal_last_name,
    pscore_legal_middle_name,
    pscore_legal_suffix,

    cast(usersdcid as int) as usersdcid,

    parse_date('%m/%d/%Y', dob) as dob,
from {{ source("powerschool_dlt", "userscorefields") }}
