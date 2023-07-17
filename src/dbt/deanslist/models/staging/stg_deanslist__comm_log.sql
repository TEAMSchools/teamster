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
    nullif(recordid, '') as `record_id`,
    nullif(callstatus, '') as `call_status`,
    nullif(callstatusid, '') as `call_status_id`,
    nullif(calltype, '') as `call_type`,
    nullif(educatorname, '') as `educator_name`,
    nullif(email, '') as `email`,
    nullif(isdraft, '') as `is_draft`,
    nullif(mailingaddress, '') as `mailing_address`,
    nullif(phonenumber, '') as `phone_number`,
    nullif(reason, '') as `reason`,
    nullif(reasonid, '') as `reason_id`,
    nullif(recordtype, '') as `record_type`,
    nullif(response, '') as `response`,
    nullif(topic, '') as `topic`,
    nullif(userid, '') as `user_id`,
    safe_cast(nullif(calldatetime, '') as datetime) as `call_date_time`,

    {# records #}
    safe_cast(
        nullif(student.secondarystudentid, '') as int
    ) as `student_secondary_student_id`,
    safe_cast(nullif(student.studentid, '') as int) as `student_student_id`,
    safe_cast(
        nullif(student.studentschoolid, '') as int
    ) as `student_student_school_id`,
    nullif(student.studentfirstname, '') as `student_student_first_name`,
    nullif(student.studentlastname, '') as `student_student_last_name`,
    nullif(student.studentmiddlename, '') as `student_student_middle_name`,

    {# repeated records #}
    followups as `followups`,
from deduplicate
