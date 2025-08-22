select
    * except (
        defaultdecimalcount,
        gradeformulasetid,
        gradesectionconfigid,
        iscalcformulaeditable,
        iscalcprecisioneditable,
        iscalcsectionfromstndedit,
        isdropscoreeditable,
        isgradescaleteachereditable,
        ishigherlvlstndeditable,
        ishigherstndautocalc,
        ishigherstndcalceditable,
        {# ismulticategoryallowed, #}
        {# ismulticategoryeditable, #}
        issectstndweighteditable,
        isstndcalcmeteditable,
        isstndrcntscoreeditable,
        isusingpercentforstndautocalc,
        minimumassignmentvalue,
        sectionsdcid
    ),

    /* column transformations */
    defaultdecimalcount.int_value as defaultdecimalcount,
    gradeformulasetid.int_value as gradeformulasetid,
    gradesectionconfigid.int_value as gradesectionconfigid,
    iscalcformulaeditable.int_value as iscalcformulaeditable,
    iscalcprecisioneditable.int_value as iscalcprecisioneditable,
    iscalcsectionfromstndedit.int_value as iscalcsectionfromstndedit,
    isdropscoreeditable.int_value as isdropscoreeditable,
    isgradescaleteachereditable.int_value as isgradescaleteachereditable,
    ishigherlvlstndeditable.int_value as ishigherlvlstndeditable,
    ishigherstndautocalc.int_value as ishigherstndautocalc,
    ishigherstndcalceditable.int_value as ishigherstndcalceditable,
    {# ismulticategoryallowed.int_value as ismulticategoryallowed, #}
    {# ismulticategoryeditable.int_value as ismulticategoryeditable, #}
    issectstndweighteditable.int_value as issectstndweighteditable,
    isstndcalcmeteditable.int_value as isstndcalcmeteditable,
    isstndrcntscoreeditable.int_value as isstndrcntscoreeditable,
    isusingpercentforstndautocalc.int_value as isusingpercentforstndautocalc,
    minimumassignmentvalue.int_value as minimumassignmentvalue,
    sectionsdcid.int_value as sectionsdcid,
from {{ source("powerschool_odbc", "src_powerschool__gradesectionconfig") }}
