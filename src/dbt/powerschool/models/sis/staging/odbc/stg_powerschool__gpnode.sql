select
    `name`,
    minimumgrade,
    gpamethod,

    /* records */
    id.int_value as id,
    parentid.int_value as parentid,
    gpversionid.int_value as gpversionid,
    nodetype.int_value as nodetype,
    altcompletioncount.int_value as altcompletioncount,
    completioncount.int_value as completioncount,
    allowanyof.int_value as allowanyof,
    allowwaiver.int_value as allowwaiver,
    ishidden.int_value as ishidden,
    issinglesitting.int_value as issinglesitting,
    issummation.int_value as issummation,
    sortorder.int_value as sortorder,
    requirementcount.int_value as requirementcount,
    verifyminimumgradefirst.int_value as verifyminimumgradefirst,

    creditcapacity.double_value as creditcapacity,
    minimumgpa.double_value as minimumgpa,
    minimumgradepercentage.double_value as minimumgradepercentage,
from {{ source("powerschool_odbc", "src_powerschool__gpnode") }}
