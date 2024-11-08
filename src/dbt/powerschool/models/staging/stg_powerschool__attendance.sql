with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__attendance"),
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
        attendance_codeid,
        calendar_dayid,
        schoolid,
        yearid,
        studentid,
        ccid,
        periodid,
        parent_attendanceid,
        att_interval,
        lock_teacher_yn,
        lock_reporting_yn,
        total_minutes,
        ada_value_code,
        ada_value_time,
        adm_value,
        programid,
        att_flags,
        whomodifiedid
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    attendance_codeid.int_value as attendance_codeid,
    calendar_dayid.int_value as calendar_dayid,
    schoolid.int_value as schoolid,
    yearid.int_value as yearid,
    studentid.int_value as studentid,
    ccid.int_value as ccid,
    periodid.int_value as periodid,
    parent_attendanceid.int_value as parent_attendanceid,
    att_interval.int_value as att_interval,
    lock_teacher_yn.int_value as lock_teacher_yn,
    lock_reporting_yn.int_value as lock_reporting_yn,
    total_minutes.int_value as total_minutes,
    ada_value_code.double_value as ada_value_code,
    ada_value_time.double_value as ada_value_time,
    adm_value.double_value as adm_value,
    programid.int_value as programid,
    att_flags.int_value as att_flags,
    whomodifiedid.int_value as whomodifiedid,
from deduplicate
