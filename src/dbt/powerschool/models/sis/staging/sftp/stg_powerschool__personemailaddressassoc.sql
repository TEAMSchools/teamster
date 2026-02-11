select
    * except (
        emailaddressid,
        emailaddresspriorityorder,
        emailtypecodesetid,
        isprimaryemailaddress,
        personemailaddressassocid,
        personid,
        whencreated,
        whenmodified,
        source_file_name
    ),

    cast(emailaddressid as int) as emailaddressid,
    cast(emailaddresspriorityorder as int) as emailaddresspriorityorder,
    cast(emailtypecodesetid as int) as emailtypecodesetid,
    cast(isprimaryemailaddress as int) as isprimaryemailaddress,
    cast(personemailaddressassocid as int) as personemailaddressassocid,
    cast(personid as int) as personid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__personemailaddressassoc") }}
