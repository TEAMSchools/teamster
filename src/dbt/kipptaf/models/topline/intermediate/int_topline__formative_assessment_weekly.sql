with
    assessment_weeks as (
        select
            rr.powerschool_student_number,
            rr.academic_year,
            rr.subject_area,
            rr.module_type,
            rr.title,
            rr.administered_at,

            cw.week_start_monday,
            cw.week_end_sunday,

            case
                when rr.is_mastery then 1 when not rr.is_mastery then 0
            end as is_mastery_int,
            row_number() over (
                partition by
                    rr.powerschool_student_number,
                    rr.academic_year,
                    rr.subject_area,
                    cw.week_start_monday
                order by cw.week_start_monday desc
            ) as rn_week_latest,
        from {{ ref("int_assessments__response_rollup") }} as rr
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on rr.academic_year = cw.academic_year
            and rr.powerschool_school_id = cw.schoolid
            and rr.administered_at between cw.week_start_monday and cw.week_end_sunday
        where rr.response_type = 'overall' and rr.module_type in ('QA', 'MQQ')
    )

select
    aw.powerschool_student_number,
    aw.academic_year,
    aw.subject_area,
    aw.module_type,
    aw.title,
    aw.administered_at,
    aw.week_start_monday,
    aw.week_end_sunday,
    aw.is_mastery_int,

    last_value(is_mastery_int ignore nulls) over (
        partition by powerschool_student_number, subject_area, academic_year
        order by week_start_monday
        rows between unbounded preceding and current row
    ) as mastery_as_of_week,
from assessment_weeks as aw
where rn_week_latest = 1
