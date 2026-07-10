with
    contacts as (
        select student_number, academic_year, schoolid, calendardate, is_successful_int,
        from {{ ref("int_topline__attendance_contacts") }}
        where
            is_enrolled_week and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    periods as (
        select
            schoolid,
            academic_year,
            period_type,
            period_label,
            period_start,
            period_end,
        from {{ ref("int_topline__periods") }}
        where org_scope = 'school' and period_type != 'week'
    )

select
    c.student_number,
    c.academic_year,
    c.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    sum(c.is_successful_int) as successful_comms_sum,
    count(c.is_successful_int) as required_comms_count,
from contacts as c
inner join
    periods as p
    on c.schoolid = p.schoolid
    and c.academic_year = p.academic_year
    and c.calendardate between p.period_start and p.period_end
group by
    c.student_number,
    c.academic_year,
    c.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
