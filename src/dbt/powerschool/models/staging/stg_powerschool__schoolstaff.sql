with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__schoolstaff"),
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
        schoolid,
        users_dcid,
        balance1,
        balance2,
        balance3,
        balance4,
        noofcurclasses,
        staffstatus,
        `status`,
        sched_maximumcourses,
        sched_maximumduty,
        sched_maximumfree,
        sched_totalcourses,
        sched_maximumconsecutive,
        sched_isteacherfree,
        sched_teachermoreoneschool,
        sched_substitute,
        sched_scheduled,
        sched_usebuilding,
        sched_usehouse,
        sched_lunch,
        sched_maxpers,
        sched_maxpreps,
        whomodifiedid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    users_dcid.int_value as users_dcid,
    balance1.double_value as balance1,
    balance2.double_value as balance2,
    balance3.double_value as balance3,
    balance4.double_value as balance4,
    noofcurclasses.int_value as noofcurclasses,
    staffstatus.int_value as staffstatus,
    status.int_value as status,
    sched_maximumcourses.int_value as sched_maximumcourses,
    sched_maximumduty.int_value as sched_maximumduty,
    sched_maximumfree.int_value as sched_maximumfree,
    sched_totalcourses.int_value as sched_totalcourses,
    sched_maximumconsecutive.int_value as sched_maximumconsecutive,
    sched_isteacherfree.int_value as sched_isteacherfree,
    sched_teachermoreoneschool.int_value as sched_teachermoreoneschool,
    sched_substitute.int_value as sched_substitute,
    sched_scheduled.int_value as sched_scheduled,
    sched_usebuilding.int_value as sched_usebuilding,
    sched_usehouse.int_value as sched_usehouse,
    sched_lunch.int_value as sched_lunch,
    sched_maxpers.int_value as sched_maxpers,
    sched_maxpreps.int_value as sched_maxpreps,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
