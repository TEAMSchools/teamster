{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    scedcode,
    subjecttype,
    aptype,
    created_by,
    created_ts,
    last_modified_by,
    last_modified_ts,

    sced_code_mappingid.int_value as sced_code_mappingid,
from {{ source("powerschool_sftp", "src_powerschool__sced_code_mapping") }}
