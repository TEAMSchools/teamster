select
    * except (
        codesetid,
        excludefromstatereporting,
        isdeletable,
        ismodifiable,
        isvisible,
        parentcodesetid,
        uidisplayorder,
        effectivestartdate,
        effectiveenddate,
        whencreated,
        whenmodified
    ),

    cast(codesetid as int) as codesetid,
    cast(excludefromstatereporting as int) as excludefromstatereporting,
    cast(isdeletable as int) as isdeletable,
    cast(ismodifiable as int) as ismodifiable,
    cast(isvisible as int) as isvisible,
    cast(parentcodesetid as int) as parentcodesetid,
    cast(uidisplayorder as int) as uidisplayorder,

    cast(effectivestartdate as date) as effectivestartdate,
    cast(effectiveenddate as date) as effectiveenddate,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__codeset") }}
