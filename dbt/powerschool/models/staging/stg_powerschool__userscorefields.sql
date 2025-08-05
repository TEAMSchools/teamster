with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__userscorefields"),
                partition_by="usersdcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

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
from deduplicate
