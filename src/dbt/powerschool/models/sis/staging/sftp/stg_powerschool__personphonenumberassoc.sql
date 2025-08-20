select
    * except (
        personphonenumberassocid,
        personid,
        phonenumberid,
        phonetypecodesetid,
        phonenumberpriorityorder,
        ispreferred
    ),

    /* column transformations */
    personphonenumberassocid.int_value as personphonenumberassocid,
    personid.int_value as personid,
    phonenumberid.int_value as phonenumberid,
    phonetypecodesetid.int_value as phonetypecodesetid,
    phonenumberpriorityorder.int_value as phonenumberpriorityorder,
    ispreferred.int_value as ispreferred,
from {{ source("powerschool_sftp", "src_powerschool__personphonenumberassoc") }}
