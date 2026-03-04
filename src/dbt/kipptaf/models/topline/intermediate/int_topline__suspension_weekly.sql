with
    calcs as (
        select
            co.student_number,
            co.academic_year,
            co.schoolid,
            co.week_start_monday,
            co.week_end_sunday,

            count(
                distinct if(ip.is_suspension, ip.incident_penalty_id, null)
            ) as suspension_count_all,
        from {{ ref("int_extracts__student_enrollments_weeks") }} as co
        left join
            {{ ref("int_deanslist__incidents__penalties") }} as ip
            on co.student_number = ip.student_school_id
            and co.academic_year = ip.create_ts_academic_year
            and co.deanslist_school_id = ip.school_id
            and ip.start_date between co.week_start_monday and co.week_end_sunday
            and ip.referral_tier not in ('Non-Behavioral', 'Social Work')
        where co.academic_year >= {{ var("current_academic_year") - 1 }}
        group by
            co.student_number,
            co.academic_year,
            co.schoolid,
            co.week_start_monday,
            co.week_end_sunday
    )

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,

    if(
        sum(suspension_count_all) over (
            partition by student_number, academic_year, schoolid
            order by week_start_monday asc
        )
        > 0,
        1,
        0
    ) as is_suspended_y1_all_running,
from calcs
