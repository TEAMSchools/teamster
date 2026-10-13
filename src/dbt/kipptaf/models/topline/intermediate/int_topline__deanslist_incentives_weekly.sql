with
    progress_weeks as (
        -- grain projection, not dup-masking
        select distinct
            student_school_id,
            academic_year,

            date_add(
                date_trunc(behavior_date, week(sunday)), interval 1 day
            ) as week_start_monday,
        from {{ ref("stg_deanslist__behavior") }}
        where
            behavior = 'Progress to Quarterly Incentive'
            and academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,

    if(pw.student_school_id is not null, 1, 0) as is_receiving_incentive,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
left join
    progress_weeks as pw
    on cw.student_number = pw.student_school_id
    and cw.academic_year = pw.academic_year
    and cw.week_start_monday = pw.week_start_monday
where cw.is_enrolled_week and cw.academic_year >= {{ var("current_academic_year") - 1 }}
