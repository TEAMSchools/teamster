select
    * except (
        gradecalculationtypeid,
        gradeformulasetid,
        isalternatepointsused,
        iscalcformulaeditable,
        isdroplowstudentfavor,
        isdropscoreeditable,
        ismulticategoryeditable,
        isnograde,
        yearid
    ),

    cast(gradecalculationtypeid as int) as gradecalculationtypeid,
    cast(gradeformulasetid as int) as gradeformulasetid,
    cast(isalternatepointsused as int) as isalternatepointsused,
    cast(iscalcformulaeditable as int) as iscalcformulaeditable,
    cast(isdroplowstudentfavor as int) as isdroplowstudentfavor,
    cast(isdropscoreeditable as int) as isdropscoreeditable,
    cast(ismulticategoryeditable as int) as ismulticategoryeditable,
    cast(isnograde as int) as isnograde,
    cast(yearid as int) as yearid,
from {{ source("powerschool_dlt", "gradecalculationtype") }}
