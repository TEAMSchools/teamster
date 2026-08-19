select
    schoolid,
    yearid,

    -- PowerSchool derives one row per calendar track (A through F) by unpivoting
    -- the calendar_day track columns. Focus has no track concept, and Miami's
    -- track is already null on every row of int_extracts__student_enrollments,
    -- so a fabricated 'A' would be no more joinable than null. One row per
    -- school-year with a null track, and the ops dashboard join is made
    -- null-safe in the kipptaf task that repoints it.
    cast(null as string) as track,

    min(date_value) as min_calendardate,
    max(date_value) as max_calendardate,
    count(date_value) as days_total,
    sum(
        if(date_value > current_date('{{ var("local_timezone") }}'), 1, 0)
    ) as days_remaining,
from {{ ref("int_focus__calendar_day") }}
group by schoolid, yearid
