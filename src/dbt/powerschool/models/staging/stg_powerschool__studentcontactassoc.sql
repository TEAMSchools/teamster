with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__studentcontactassoc"
                ),
                partition_by="studentcontactassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        studentcontactassocid,
        studentdcid,
        personid,
        contactpriorityorder,
        currreltypecodesetid
    ),

    /* column transformations */
    studentcontactassocid.int_value as studentcontactassocid,
    studentdcid.int_value as studentdcid,
    personid.int_value as personid,
    contactpriorityorder.int_value as contactpriorityorder,
    currreltypecodesetid.int_value as currreltypecodesetid,
from deduplicate
