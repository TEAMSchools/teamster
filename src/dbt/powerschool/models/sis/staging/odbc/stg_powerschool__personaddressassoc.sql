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
from {{ source("powerschool_odbc", "src_powerschool__personaddressassoc") }}
