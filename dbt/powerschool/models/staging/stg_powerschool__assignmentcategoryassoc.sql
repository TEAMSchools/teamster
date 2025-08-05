with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__assignmentcategoryassoc"
                ),
                partition_by="assignmentcategoryassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        assignmentcategoryassocid,
        assignmentsectionid,
        teachercategoryid,
        yearid,
        isprimary,
        whomodifiedid
    ),

    /* column transformations */
    assignmentcategoryassocid.int_value as assignmentcategoryassocid,
    assignmentsectionid.int_value as assignmentsectionid,
    teachercategoryid.int_value as teachercategoryid,
    yearid.int_value as yearid,
    isprimary.int_value as isprimary,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
