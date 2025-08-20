{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

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
from {{ source("powerschool_odbc", "src_powerschool__districtteachercategory") }}
