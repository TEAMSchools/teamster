with
    enrollments as (
        select distinct student_number, academic_year, schoolid, deanslist_school_id,
        from {{ ref("int_extracts__student_enrollments_weeks") }}
        where academic_year >= {{ var("current_academic_year") - 1 }}
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
    e.student_number,
    e.academic_year,
    e.schoolid,

    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end,

    if(
        count(distinct if(ip.is_suspension, ip.incident_penalty_id, null)) > 0, 1, 0
    ) as is_suspended_period_int,
from enrollments as e
inner join periods as p on e.schoolid = p.schoolid and e.academic_year = p.academic_year
left join
    {{ ref("int_deanslist__incidents__penalties") }} as ip
    on e.student_number = ip.student_school_id
    and e.academic_year = ip.create_ts_academic_year
    and e.deanslist_school_id = ip.school_id
    and ip.start_date between p.period_start and p.period_end
    and ip.referral_tier not in ('Non-Behavioral', 'Social Work')
group by
    e.student_number,
    e.academic_year,
    e.schoolid,
    p.period_type,
    p.period_label,
    p.period_start,
    p.period_end
