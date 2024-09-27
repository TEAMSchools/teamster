with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__personemailaddressassoc"
                ),
                partition_by="personemailaddressassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        personemailaddressassocid,
        personid,
        emailaddressid,
        emailtypecodesetid,
        isprimaryemailaddress,
        emailaddresspriorityorder
    ),

    /* column transformations */
    personemailaddressassocid.int_value as personemailaddressassocid,
    personid.int_value as personid,
    emailaddressid.int_value as emailaddressid,
    emailtypecodesetid.int_value as emailtypecodesetid,
    isprimaryemailaddress.int_value as isprimaryemailaddress,
    emailaddresspriorityorder.int_value as emailaddresspriorityorder,
from deduplicate
