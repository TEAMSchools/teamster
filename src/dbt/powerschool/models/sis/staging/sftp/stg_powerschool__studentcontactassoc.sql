{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        studentcontactassocid,
        studentdcid,
        personid,
        contactpriorityorder,
        currreltypecodesetid
    ),

    /* column transformations */
    studentcontactassocid.int_value as studentcontactassocid,
    studentdcid.int_value as studentdcid,
    personid.int_value as personid,
    contactpriorityorder.int_value as contactpriorityorder,
    currreltypecodesetid.int_value as currreltypecodesetid,
from {{ source("powerschool", "src_powerschool__studentcontactassoc") }}
