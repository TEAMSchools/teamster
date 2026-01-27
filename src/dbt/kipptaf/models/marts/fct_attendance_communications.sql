with
    completed_calls as (
        select
            *,
            row_number() over (
                partition by student_school_id, call_date order by call_date_time desc
            ) as rn_date,
        from {{ ref("int_deanslist__comm_log") }}
        where is_attendance_call and call_status = 'Completed'
    ),

    {# assigning success status just to most recent completed call #}
    final as (
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
                student_school_id is not null and reason not like 'Att: Unknown%',
                true,
                false
            ) as is_successful,
            if(
                student_school_id is not null and reason not like 'Att: Unknown%', 1, 0
            ) as is_successful_int,
        from completed_calls
        where rn_date = 1
    )

select *,
from final
