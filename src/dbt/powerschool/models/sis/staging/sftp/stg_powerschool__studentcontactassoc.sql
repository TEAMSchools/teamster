select
    * except (
        contactpriorityorder,
        currreltypecodesetid,
        personid,
        studentcontactassocid,
        studentdcid,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(contactpriorityorder as int) as contactpriorityorder,
    cast(currreltypecodesetid as int) as currreltypecodesetid,
    cast(personid as int) as personid,
    cast(studentcontactassocid as int) as studentcontactassocid,
    cast(studentdcid as int) as studentdcid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__studentcontactassoc") }}
