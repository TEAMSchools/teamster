select
    * except (
        dcid,
        excludefromstatereporting,
        gendercodesetid,
        id,
        isactive,
        prefixcodesetid,
        statecontactnumber,
        suffixcodesetid,
        whencreated,
        whenmodified
    ),

    cast(dcid as int) as dcid,
    cast(excludefromstatereporting as int) as excludefromstatereporting,
    cast(gendercodesetid as int) as gendercodesetid,
    cast(id as int) as id,
    cast(isactive as int) as isactive,
    cast(prefixcodesetid as int) as prefixcodesetid,
    cast(statecontactnumber as int) as statecontactnumber,
    cast(suffixcodesetid as int) as suffixcodesetid,

    cast(whencreated as timestamp) as whencreated,
    cast(whenmodified as timestamp) as whenmodified,
from {{ source("powerschool_sftp", "src_powerschool__person") }}
