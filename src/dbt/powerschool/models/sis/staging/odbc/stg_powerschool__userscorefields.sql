select
    gender,
    photolastupdated,
    pscore_legal_first_name,
    pscore_legal_gender,
    pscore_legal_last_name,
    pscore_legal_middle_name,
    pscore_legal_suffix,

    /* records */
    usersdcid.int_value as usersdcid,

    /* transformations */
    parse_date('%m/%d/%Y', dob) as dob,
from {{ source("powerschool_odbc", "src_powerschool__userscorefields") }}
