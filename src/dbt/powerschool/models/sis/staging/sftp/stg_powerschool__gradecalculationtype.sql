select
    * except (
        gradecalculationtypeid,
        gradeformulasetid,
        yearid,
        isnograde,
        isdroplowstudentfavor,
        isalternatepointsused,
        iscalcformulaeditable,
        isdropscoreeditable
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
from {{ source("powerschool_sftp", "src_powerschool__gradecalculationtype") }}
