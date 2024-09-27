with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__gradecalcformulaweight"
                ),
                partition_by="gradecalcformulaweightid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        gradecalcformulaweightid,
        gradecalculationtypeid,
        teachercategoryid,
        districtteachercategoryid,
        assignmentid,
        `weight`
    ),

    /* column transformations */
    gradecalcformulaweightid.int_value as gradecalcformulaweightid,
    gradecalculationtypeid.int_value as gradecalculationtypeid,
    teachercategoryid.int_value as teachercategoryid,
    districtteachercategoryid.int_value as districtteachercategoryid,
    assignmentid.int_value as assignmentid,
    weight.bytes_decimal_value as `weight`,
from deduplicate
