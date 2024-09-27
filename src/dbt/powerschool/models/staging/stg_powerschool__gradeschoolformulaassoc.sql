with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__gradeschoolformulaassoc"
                ),
                partition_by="gradeschoolformulaassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
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
from deduplicate
