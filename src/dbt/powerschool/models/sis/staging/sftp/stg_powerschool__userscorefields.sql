{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    dob,
    gender,
    photolastupdated,
    pscore_legal_first_name,
    pscore_legal_gender,
    pscore_legal_last_name,
    pscore_legal_middle_name,
    pscore_legal_suffix,

    /* records */
    usersdcid.int_value as usersdcid,
from {{ source("powerschool_sftp", "src_powerschool__userscorefields") }}
