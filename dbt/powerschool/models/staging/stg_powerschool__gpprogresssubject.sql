select
    isgroupsatisfied,
    istestgroupwaived,
    mingpamet,
    nodegpa,
    testnodepassed,

    /* records */
    id.int_value as id,
    studentsdcid.int_value as studentsdcid,
    gpnodeid.int_value as gpnodeid,
    nodetype.int_value as nodetype,
    requiredcredits.double_value as requiredcredits,
    enrolledcredits.double_value as enrolledcredits,
    requestedcredits.double_value as requestedcredits,
    earnedcredits.double_value as earnedcredits,
    waivedcredits.double_value as waivedcredits,
    appliedwaivedcredits.double_value as appliedwaivedcredits,
    isadvancedplan.int_value as isadvancedplan,
    issinglesitting.int_value as issinglesitting,
    issummation.int_value as issummation,
from {{ source("powerschool", "src_powerschool__gpprogresssubject") }}
