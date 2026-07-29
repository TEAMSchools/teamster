with
    daily as (
        select
            student_number,
            schoolid,
            academic_year,
            calendardate,
            attendancevalue,
            membershipvalue,

            if(is_truant, 1, 0) as is_truant_int,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            attendancevalue is not null
            and calendardate >= '{{ var("current_academic_year") - 1 }}-07-01'
            and calendardate < current_date('{{ var("local_timezone") }}')
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
    d.student_number,
    d.academic_year,
    d.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    sum(d.attendancevalue) as attendance_value_sum,
    sum(d.membershipvalue) as membership_value_sum,
    max(d.is_truant_int) as is_truant_period_int,

    round(safe_divide(sum(d.attendancevalue), sum(d.membershipvalue)), 3) as ada_period,

    if(
        safe_divide(sum(d.attendancevalue), sum(d.membershipvalue)) <= 0.90, 1, 0
    ) as is_chronically_absent_period_int,
from daily as d
inner join
    periods as p
    on d.schoolid = p.schoolid
    and d.academic_year = p.academic_year
    and d.calendardate between p.period_start and p.period_end
group by
    d.student_number,
    d.academic_year,
    d.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
