with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__comm_log"),
                partition_by="recordid",
                order_by="_file_name desc",
            )
        }}
    ),

    transformations as (
        select
            _dagster_partition_school as dl_school_id,
            isdraft as is_draft,

            /* repeated records */
            followups,

            /* transformations */
            cast(recordid as int) as record_id,
            cast(callstatusid as int) as call_status_id,
            cast(reasonid as int) as reason_id,
            cast(userid as int) as user_id,

            cast(nullif(calldatetime, '') as datetime) as call_date_time,

            cast(nullif(student.secondarystudentid, '') as int) as secondary_student_id,
            cast(nullif(student.studentid, '') as int) as student_id,
            cast(nullif(student.studentschoolid, '') as int) as student_school_id,

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
        from deduplicate
    )

select
    *,

    cast(call_date_time as date) as call_date,

    {{
        date_to_fiscal_year(
            date_field="call_date_time", start_month=7, year_source="start"
        )
    }} as academic_year,
from transformations
