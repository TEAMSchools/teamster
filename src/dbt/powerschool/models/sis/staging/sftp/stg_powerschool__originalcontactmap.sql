{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (originalcontactmapid, studentcontactassocid),

    /* column transformations */
    originalcontactmapid.int_value as originalcontactmapid,
    studentcontactassocid.int_value as studentcontactassocid,
from {{ source("powerschool_sftp", "src_powerschool__originalcontactmap") }}
