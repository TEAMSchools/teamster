select
    student_number,
    academic_year,

    count(school_date) as days_in_session,
    sum(state_value) as days_present,
    sum(abs(state_value - 1)) as days_absent,
    avg(state_value) as ada,
from {{ ref("int_focus__attendance_daily") }}
where school_date <= current_date('{{ var("local_timezone") }}')
group by student_number, academic_year
