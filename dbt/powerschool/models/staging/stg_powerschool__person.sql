with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__person"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        dcid,
        id,
        prefixcodesetid,
        suffixcodesetid,
        gendercodesetid,
        statecontactnumber,
        isactive,
        excludefromstatereporting
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    prefixcodesetid.int_value as prefixcodesetid,
    suffixcodesetid.int_value as suffixcodesetid,
    gendercodesetid.int_value as gendercodesetid,
    statecontactnumber.int_value as statecontactnumber,
    isactive.int_value as isactive,
    excludefromstatereporting.int_value as excludefromstatereporting,
from deduplicate
