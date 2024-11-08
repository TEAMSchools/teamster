with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__gradecalculationtype"
                ),
                partition_by="gradecalculationtypeid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
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
from deduplicate
