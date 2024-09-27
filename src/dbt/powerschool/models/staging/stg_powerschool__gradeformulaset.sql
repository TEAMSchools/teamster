with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__gradeformulaset"),
                partition_by="gradeformulasetid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
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
from deduplicate
