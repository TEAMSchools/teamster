with
    comm_by_week as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,

            sum(is_successful_int) as successful_comms_sum,
            count(is_successful_int) as required_comms_count,
        from {{ ref("int_topline__attendance_contacts") }}
        where is_enrolled_week
        group by student_number, academic_year, week_start_monday, week_end_sunday
    )

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    sum(successful_comms_sum) over (
        partition by academic_year, student_number order by week_start_monday asc
    ) as successful_comms_sum_running,

    sum(required_comms_count) over (
        partition by academic_year, student_number order by week_start_monday asc
    ) as required_comms_count_running,
from comm_by_week
