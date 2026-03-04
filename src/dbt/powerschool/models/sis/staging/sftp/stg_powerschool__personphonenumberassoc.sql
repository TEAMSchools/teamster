select
    * except (
        ispreferred,
        personid,
        personphonenumberassocid,
        phonenumberid,
        phonenumberpriorityorder,
        phonetypecodesetid,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(ispreferred as int) as ispreferred,
    cast(personid as int) as personid,
    cast(personphonenumberassocid as int) as personphonenumberassocid,
    cast(phonenumberid as int) as phonenumberid,
    cast(phonenumberpriorityorder as int) as phonenumberpriorityorder,
    cast(phonetypecodesetid as int) as phonetypecodesetid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__personphonenumberassoc") }}
