select
    * except (
        defaultdaysbeforedue,
        displayposition,
        districtteachercategoryid,
        isactive,
        isdefaultpublishscores,
        isinfinalgrades,
        isusermodifiable,
        whomodifiedid
    ),

    cast(defaultdaysbeforedue as int) as defaultdaysbeforedue,
    cast(displayposition as int) as displayposition,
    cast(districtteachercategoryid as int) as districtteachercategoryid,
    cast(isactive as int) as isactive,
    cast(isdefaultpublishscores as int) as isdefaultpublishscores,
    cast(isinfinalgrades as int) as isinfinalgrades,
    cast(isusermodifiable as int) as isusermodifiable,
    cast(whomodifiedid as int) as whomodifiedid,
from {{ source("powerschool_dlt", "districtteachercategory") }}
