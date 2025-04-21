select
    `name`,
    minimumgrade,
    gpamethod,

    /* records */
    id.int_value as id,
    parentid.int_value as parentid,
    gpversionid.int_value as gpversionid,
    nodetype.int_value as nodetype,
    creditcapacity.double_value as creditcapacity,
    altcompletioncount.int_value as altcompletioncount,
    completioncount.int_value as completioncount,
    allowanyof.int_value as allowanyof,
    allowwaiver.int_value as allowwaiver,
    ishidden.int_value as ishidden,
    issinglesitting.int_value as issinglesitting,
    issummation.int_value as issummation,
    sortorder.int_value as sortorder,

    minimumgpa,
    minimumgradepercentage,
    requirementcount,
    verifyminimumgradefirst,
from {{ source("powerschool", "src_powerschool__gpnode") }}
