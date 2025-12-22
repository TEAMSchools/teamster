with
    comm_log as (select * from {{ ref("int_deanslist__comm_log") }}),

    row_number as (
        select
            student_school_id,
            student_id,
            dl_school_id,
            call_date as commlog_date,
            educator_name as commlog_staff_name,
            reason as commlog_reason,
            response as commlog_notes,
            topic as commlog_topic,
            call_type as commlog_type,
            call_status as commlog_status,
            is_attendance_call,
            is_truancy_call,

            if(
                student_school_id is not null and reason not like 'Att: Unknown%',
                true,
                false
            ) as is_successful,

            if(
                student_school_id is not null and reason not like 'Att: Unknown%', 1, 0
            ) as is_successful_int,

            row_number() over (
                partition by student_school_id, call_date order by call_date_time desc
            ) as rn_date,
        from {{ ref("int_deanslist__comm_log") }}
        where is_attendance_call and call_status = 'Completed'
    ),

    final as (select *, from comm_log where rn_date = 1)

select *,
from final
