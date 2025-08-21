select
    * except (
        adminldapenabled,
        allowloginend,
        allowloginstart,
        dcid,
        fedethnicity,
        fedracedecline,
        gradebooktype,
        homeschoolid,
        maximum_load,
        numlogins,
        photo,
        prefixcodesetid,
        psaccess,
        ptaccess,
        supportcontact,
        teacherldapenabled,
        whomodifiedid,
        wm_createtime,
        wm_exclude,
        wm_tier,
        lunch_id,
        wm_createdate,
        wm_statusdate,
        wm_ta_date,
        transaction_date
    ),

    cast(adminldapenabled as int) as adminldapenabled,
    cast(allowloginend as int) as allowloginend,
    cast(allowloginstart as int) as allowloginstart,
    cast(dcid as int) as dcid,
    cast(fedethnicity as int) as fedethnicity,
    cast(fedracedecline as int) as fedracedecline,
    cast(gradebooktype as int) as gradebooktype,
    cast(homeschoolid as int) as homeschoolid,
    cast(maximum_load as int) as maximum_load,
    cast(numlogins as int) as numlogins,
    cast(photo as int) as photo,
    cast(prefixcodesetid as int) as prefixcodesetid,
    cast(psaccess as int) as psaccess,
    cast(ptaccess as int) as ptaccess,
    cast(supportcontact as int) as supportcontact,
    cast(teacherldapenabled as int) as teacherldapenabled,
    cast(whomodifiedid as int) as whomodifiedid,
    cast(wm_createtime as int) as wm_createtime,
    cast(wm_exclude as int) as wm_exclude,
    cast(wm_tier as int) as wm_tier,

    cast(lunch_id as float64) as lunch_id,

    cast(wm_createdate as date) as wm_createdate,
    cast(wm_statusdate as date) as wm_statusdate,
    cast(wm_ta_date as date) as wm_ta_date,

    cast(transaction_date as timestamp) as transaction_date,
{#
| access             | STRING          |               | missing in contract   |
| group              | STRING          |               | missing in contract   |
| accessvalue        |                 | STRING        | missing in definition |
| executionid        |                 | STRING        | missing in definition |
| groupvalue         |                 | INT64         | missing in definition |
| whencreated        |                 | TIMESTAMP     | missing in definition |
| whenmodified       |                 | TIMESTAMP     | missing in definition |
| whocreated         |                 | STRING        | missing in definition |
| whomodified        |                 | STRING        | missing in definition |
#}
from {{ source("powerschool_sftp", "src_powerschool__users") }}
