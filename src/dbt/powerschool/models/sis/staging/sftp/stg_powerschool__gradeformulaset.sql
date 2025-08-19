{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        gradeformulasetid,
        yearid,
        iscoursegradecalculated,
        isreporttermsetupsame,
        sectionsdcid
    ),

    /* column transformations */
    gradeformulasetid.int_value as gradeformulasetid,
    yearid.int_value as yearid,
    iscoursegradecalculated.int_value as iscoursegradecalculated,
    isreporttermsetupsame.int_value as isreporttermsetupsame,
    sectionsdcid.int_value as sectionsdcid,
from {{ source("powerschool", "src_powerschool__gradeformulaset") }}
