{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        personemailaddressassocid,
        personid,
        emailaddressid,
        emailtypecodesetid,
        isprimaryemailaddress,
        emailaddresspriorityorder
    ),

    /* column transformations */
    personemailaddressassocid.int_value as personemailaddressassocid,
    personid.int_value as personid,
    emailaddressid.int_value as emailaddressid,
    emailtypecodesetid.int_value as emailtypecodesetid,
    isprimaryemailaddress.int_value as isprimaryemailaddress,
    emailaddresspriorityorder.int_value as emailaddresspriorityorder,
from {{ source("powerschool", "src_powerschool__personemailaddressassoc") }}
