with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__comm_log"),
                partition_by="RecordID",
                order_by="_file_name desc",
            )
        }}
    )

select
    isdraft as is_draft,

    /* repeated records */
    followups,

    /* transformations */
    safe_cast(recordid as int) as record_id,
    safe_cast(callstatusid as int) as call_status_id,
    safe_cast(reasonid as int) as reason_id,
    safe_cast(userid as int) as user_id,

    nullif(callstatus, '') as call_status,
    nullif(calltype, '') as call_type,
    nullif(educatorname, '') as educator_name,
    nullif(email, '') as email,
    nullif(mailingaddress, '') as mailing_address,
    nullif(phonenumber, '') as phone_number,
    nullif(reason, '') as reason,
    nullif(recordtype, '') as record_type,
    nullif(response, '') as response,
    nullif(topic, '') as topic,

    nullif(student.studentfirstname, '') as student_first_name,
    nullif(student.studentmiddlename, '') as student_middle_name,
    nullif(student.studentlastname, '') as student_last_name,

    safe_cast(nullif(calldatetime, '') as datetime) as call_date_time,

    safe_cast(nullif(student.secondarystudentid, '') as int) as secondary_student_id,
    safe_cast(nullif(student.studentid, '') as int) as student_id,
    safe_cast(nullif(student.studentschoolid, '') as int) as student_school_id,
from deduplicate
