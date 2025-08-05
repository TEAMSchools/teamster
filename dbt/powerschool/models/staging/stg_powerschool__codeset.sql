with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__codeset"),
                partition_by="codesetid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        codesetid,
        parentcodesetid,
        uidisplayorder,
        isvisible,
        ismodifiable,
        isdeletable,
        excludefromstatereporting
    ),

    /* column transformations */
    codesetid.int_value as codesetid,
    parentcodesetid.int_value as parentcodesetid,
    uidisplayorder.int_value as uidisplayorder,
    isvisible.int_value as isvisible,
    ismodifiable.int_value as ismodifiable,
    isdeletable.int_value as isdeletable,
    excludefromstatereporting.int_value as excludefromstatereporting,
from deduplicate
