with
    call_completion as (
        select
            student_school_id as student_number,
            call_date as commlog_date,
            educator_name as commlog_staff_name,
            reason as commlog_reason,
            response as commlog_notes,
            topic as commlog_topic,
            call_type as commlog_type,
            call_status as commlog_status,

            if(
                com.student_school_id is not null
                and com.reason not like 'Att: Unknown%',
                true,
                false
            ) as is_successful,

            if(
                com.student_school_id is not null
                and com.reason not like 'Att: Unknown%',
                1,
                0
            ) as is_successful_int,

            row_number() over (
                partition by student_school_id, call_date order by call_date_time desc
            ) as rn_date,
        from {{ ref("int_deanslist__comm_log") }}
        where is_attendance_call and call_status = 'Completed'
    ),

    final as (
        select
            student_number,
            commlog_date,
            commlog_staff_name,
            commlog_reason,
            commlog_notes,
            commlog_topic,
            commlog_type,
            commlog_status,
            is_successful,
            is_successful_int,
        from call_completion
        where rn = 1
    )

select *,
from final
