select
    * except (
        dcid,
        id,
        noofcurclasses,
        sched_isteacherfree,
        sched_lunch,
        sched_maximumconsecutive,
        sched_maximumcourses,
        sched_maximumduty,
        sched_maximumfree,
        sched_maxpers,
        sched_maxpreps,
        sched_scheduled,
        sched_substitute,
        sched_teachermoreoneschool,
        sched_totalcourses,
        sched_usebuilding,
        sched_usehouse,
        schoolid,
        staffstatus,
        `status`,
        users_dcid,
        whomodifiedid,
        balance1,
        balance2,
        balance3,
        balance4,
        transaction_date
    ),

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(noofcurclasses as int) as noofcurclasses,
    cast(sched_isteacherfree as int) as sched_isteacherfree,
    cast(sched_lunch as int) as sched_lunch,
    cast(sched_maximumconsecutive as int) as sched_maximumconsecutive,
    cast(sched_maximumcourses as int) as sched_maximumcourses,
    cast(sched_maximumduty as int) as sched_maximumduty,
    cast(sched_maximumfree as int) as sched_maximumfree,
    cast(sched_maxpers as int) as sched_maxpers,
    cast(sched_maxpreps as int) as sched_maxpreps,
    cast(sched_scheduled as int) as sched_scheduled,
    cast(sched_substitute as int) as sched_substitute,
    cast(sched_teachermoreoneschool as int) as sched_teachermoreoneschool,
    cast(sched_totalcourses as int) as sched_totalcourses,
    cast(sched_usebuilding as int) as sched_usebuilding,
    cast(sched_usehouse as int) as sched_usehouse,
    cast(schoolid as int) as schoolid,
    cast(staffstatus as int) as staffstatus,
    cast(`status` as int) as `status`,
    cast(users_dcid as int) as users_dcid,
    cast(whomodifiedid as int) as whomodifiedid,

    cast(balance1 as float64) as balance1,
    cast(balance2 as float64) as balance2,
    cast(balance3 as float64) as balance3,
    cast(balance4 as float64) as balance4,

    cast(transaction_date as timestamp) as transaction_date,

{#
| custom                     |                 | STRING        | missing in definition |
| executionid                |                 | STRING        | missing in definition |
| whencreated                |                 | TIMESTAMP     | missing in definition |
| whenmodified               |                 | TIMESTAMP     | missing in definition |
| whocreated                 |                 | STRING        | missing in definition |
| whomodified                |                 | STRING        | missing in definition |
#}
from {{ source("powerschool_sftp", "src_powerschool__schoolstaff") }}
