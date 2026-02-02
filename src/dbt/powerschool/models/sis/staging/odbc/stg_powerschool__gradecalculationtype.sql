select
    * except (
        gradecalculationtypeid,
        gradeformulasetid,
        yearid,
        isnograde,
        isdroplowstudentfavor,
        isalternatepointsused,
        iscalcformulaeditable,
        isdropscoreeditable,
        ismulticategoryeditable
    ),

    /* column transformations */
    gradecalculationtypeid.int_value as gradecalculationtypeid,
    gradeformulasetid.int_value as gradeformulasetid,
    yearid.int_value as yearid,
    isnograde.int_value as isnograde,
    isdroplowstudentfavor.int_value as isdroplowstudentfavor,
    isalternatepointsused.int_value as isalternatepointsused,
    iscalcformulaeditable.int_value as iscalcformulaeditable,
    isdropscoreeditable.int_value as isdropscoreeditable,
    ismulticategoryeditable.int_value as ismulticategoryeditable,
from {{ source("powerschool_odbc", "src_powerschool__gradecalculationtype") }}
