select
    * except (
        alternate_school_number,
        dcid,
        dfltnextschool,
        district_number,
        fee_exemption_status,
        high_grade,
        hist_high_grade,
        hist_low_grade,
        id,
        issummerschool,
        low_grade,
        school_number,
        schoolcategorycodesetid,
        schoolgroup,
        sortorder,
        state_excludefromreporting,
        transaction_date,
        view_in_portal,
        whomodifiedid
    ),

    cast(alternate_school_number as int) as alternate_school_number,
    cast(dcid as int) as dcid,
    cast(dfltnextschool as int) as dfltnextschool,
    cast(district_number as int) as district_number,
    cast(fee_exemption_status as int) as fee_exemption_status,
    cast(high_grade as int) as high_grade,
    cast(hist_high_grade as int) as hist_high_grade,
    cast(hist_low_grade as int) as hist_low_grade,
    cast(id as int) as id,
    cast(issummerschool as int) as issummerschool,
    cast(low_grade as int) as low_grade,
    cast(school_number as int) as school_number,
    cast(schoolcategorycodesetid as int) as schoolcategorycodesetid,
    cast(schoolgroup as int) as schoolgroup,
    cast(sortorder as int) as sortorder,
    cast(state_excludefromreporting as int) as state_excludefromreporting,
    cast(view_in_portal as int) as view_in_portal,
    cast(whomodifiedid as int) as whomodifiedid,

    cast(transaction_date as timestamp) as transaction_date,

{#
| custom | | STRING | missing in definition |
| executionid | | STRING | missing in definition |
| school_level | | STRING | missing in definition |
#}
from {{ source("powerschool_sftp", "src_powerschool__schools") }}
