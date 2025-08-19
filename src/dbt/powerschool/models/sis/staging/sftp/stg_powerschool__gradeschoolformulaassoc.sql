{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        gradeschoolformulaassocid,
        gradeformulasetid,
        gradeschoolconfigid,
        isdefaultformulaset
    ),

    /* column transformations */
    gradeschoolformulaassocid.int_value as gradeschoolformulaassocid,
    gradeformulasetid.int_value as gradeformulasetid,
    gradeschoolconfigid.int_value as gradeschoolconfigid,
    isdefaultformulaset.int_value as isdefaultformulaset,
from {{ source("powerschool", "src_powerschool__gradeschoolformulaassoc") }}
