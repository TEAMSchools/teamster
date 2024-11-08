select
    gpamethod,
    minimumgrade,

    /* records */
    minimumgpa,
    sourceid,
    useallcoursesforgpacalc,

    id.int_value as id,
    gradplanid.int_value as gradplanid,
    startyear.int_value as startyear,
    endyear.int_value as endyear,
    minimumgradepercentage.double_value as minimumgradepercentage,
    verifyminimumgradefirst.int_value as verifyminimumgradefirst,
    isadvancedplan.int_value as isadvancedplan,
from {{ source("powerschool", "src_powerschool__gpversion") }}
