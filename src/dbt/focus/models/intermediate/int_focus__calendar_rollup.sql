select
    schoolid,
    academic_year,

    min(school_date) as min_school_date,
    max(school_date) as max_school_date,
    count(school_date) as days_total,
    sum(
        if(school_date > current_date('{{ var("local_timezone") }}'), 1, 0)
    ) as days_remaining,
from {{ ref("int_focus__calendar_day") }}
group by schoolid, academic_year
