select
    `name`,
    minimumgrade,
    gpamethod,

    /* records */
    minimumgpa,
    minimumgradepercentage,
    requirementcount,
    verifyminimumgradefirst,

    allowanyof.int_value as allowanyof,
    allowwaiver.int_value as allowwaiver,
    altcompletioncount.int_value as altcompletioncount,
    completioncount.int_value as completioncount,
    gpversionid.int_value as gpversionid,
    id.int_value as id,
    ishidden.int_value as ishidden,
    issinglesitting.int_value as issinglesitting,
    issummation.int_value as issummation,
    nodetype.int_value as nodetype,
    sortorder.int_value as sortorder,
    creditcapacity.double_value as creditcapacity,
    parentid.int_value as parentid,
from {{ source("powerschool", "src_powerschool__gpnode") }}
