select
    gpamethod,
    minimumgrade,

    /* records */
    id.int_value as id,
    gradplanid.int_value as gradplanid,
    startyear.int_value as startyear,
    endyear.int_value as endyear,
    minimumgradepercentage.double_value as minimumgradepercentage,
    verifyminimumgradefirst.int_value as verifyminimumgradefirst,
    isadvancedplan.int_value as isadvancedplan,

    minimumgpa,
    sourceid,
    useallcoursesforgpacalc,
from {{ source("powerschool", "src_powerschool__gpversion") }}
