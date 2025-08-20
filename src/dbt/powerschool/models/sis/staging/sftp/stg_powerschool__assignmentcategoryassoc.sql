{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select *,
from {{ source("powerschool_sftp", "src_powerschool__assignmentcategoryassoc") }}
