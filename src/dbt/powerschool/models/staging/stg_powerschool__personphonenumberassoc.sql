with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__personphonenumberassoc"
                ),
                partition_by="personphonenumberassocid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        personphonenumberassocid,
        personid,
        phonenumberid,
        phonetypecodesetid,
        phonenumberpriorityorder,
        ispreferred
    ),

    /* column transformations */
    personphonenumberassocid.int_value as personphonenumberassocid,
    personid.int_value as personid,
    phonenumberid.int_value as phonenumberid,
    phonetypecodesetid.int_value as phonetypecodesetid,
    phonenumberpriorityorder.int_value as phonenumberpriorityorder,
    ispreferred.int_value as ispreferred,
from deduplicate
