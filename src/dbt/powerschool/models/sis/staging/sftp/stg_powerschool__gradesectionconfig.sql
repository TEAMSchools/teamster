{{ config(enabled=(var("powerschool_external_source_type") == "sftp")) }}

select
    * except (
        gradesectionconfigid,
        sectionsdcid,
        gradeformulasetid,
        defaultdecimalcount,
        iscalcformulaeditable,
        isdropscoreeditable,
        iscalcprecisioneditable,
        isstndcalcmeteditable,
        isstndrcntscoreeditable,
        ishigherlvlstndeditable,
        ishigherstndautocalc,
        ishigherstndcalceditable,
        iscalcsectionfromstndedit,
        issectstndweighteditable,
        minimumassignmentvalue,
        isgradescaleteachereditable,
        isusingpercentforstndautocalc
    ),

    /* column transformations */
    gradesectionconfigid.int_value as gradesectionconfigid,
    sectionsdcid.int_value as sectionsdcid,
    gradeformulasetid.int_value as gradeformulasetid,
    defaultdecimalcount.int_value as defaultdecimalcount,
    iscalcformulaeditable.int_value as iscalcformulaeditable,
    isdropscoreeditable.int_value as isdropscoreeditable,
    iscalcprecisioneditable.int_value as iscalcprecisioneditable,
    isstndcalcmeteditable.int_value as isstndcalcmeteditable,
    isstndrcntscoreeditable.int_value as isstndrcntscoreeditable,
    ishigherlvlstndeditable.int_value as ishigherlvlstndeditable,
    ishigherstndautocalc.int_value as ishigherstndautocalc,
    ishigherstndcalceditable.int_value as ishigherstndcalceditable,
    iscalcsectionfromstndedit.int_value as iscalcsectionfromstndedit,
    issectstndweighteditable.int_value as issectstndweighteditable,
    minimumassignmentvalue.int_value as minimumassignmentvalue,
    isgradescaleteachereditable.int_value as isgradescaleteachereditable,
    isusingpercentforstndautocalc.int_value as isusingpercentforstndautocalc,
from {{ source("powerschool_sftp", "src_powerschool__gradesectionconfig") }}
