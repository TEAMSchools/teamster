with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source(
                    "powerschool", "src_powerschool__districtteachercategory"
                ),
                partition_by="districtteachercategoryid.int_value",
                order_by="_file_name desc",
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    * except (
        districtteachercategoryid,
        isinfinalgrades,
        isactive,
        isusermodifiable,
        displayposition,
        defaultscoreentrypoints,
        defaultextracreditpoints,
        defaultweight,
        defaulttotalvalue,
        isdefaultpublishscores,
        defaultdaysbeforedue,
        whomodifiedid
    ),

    /* column transformations */
    districtteachercategoryid.int_value as districtteachercategoryid,
    isinfinalgrades.int_value as isinfinalgrades,
    isactive.int_value as isactive,
    isusermodifiable.int_value as isusermodifiable,
    displayposition.int_value as displayposition,
    defaultscoreentrypoints.bytes_decimal_value as defaultscoreentrypoints,
    defaultextracreditpoints.bytes_decimal_value as defaultextracreditpoints,
    defaultweight.bytes_decimal_value as defaultweight,
    defaulttotalvalue.bytes_decimal_value as defaulttotalvalue,
    isdefaultpublishscores.int_value as isdefaultpublishscores,
    defaultdaysbeforedue.int_value as defaultdaysbeforedue,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
