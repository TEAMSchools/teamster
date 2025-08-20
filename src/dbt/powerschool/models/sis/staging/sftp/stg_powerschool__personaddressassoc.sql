{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        personaddressassocid,
        personid,
        personaddressid,
        addresstypecodesetid,
        addresspriorityorder
    ),

    /* column transformations */
    personaddressassocid.int_value as personaddressassocid,
    personid.int_value as personid,
    personaddressid.int_value as personaddressid,
    addresstypecodesetid.int_value as addresstypecodesetid,
    addresspriorityorder.int_value as addresspriorityorder,
from {{ source("powerschool_sftp", "src_powerschool__personaddressassoc") }}
