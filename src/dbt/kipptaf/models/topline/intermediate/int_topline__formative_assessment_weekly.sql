with
    student_weeks as (
        select
            rr.powerschool_student_number,
            rr.academic_year,

            cw.week_start_monday,
            cw.week_end_sunday,
        from {{ ref("int_assessments__response_rollup") }} as rr
        inner join
            {{ ref("int_powerschool__calendar_week") }} as cw
            on rr.powerschool_school_id = cw.schoolid
            and rr.academic_year = cw.academic_year
        group by all
    ),

    assessment_weeks as (
        select
            sw.powerschool_student_number,
            sw.academic_year,
            sw.week_start_monday,
            sw.week_end_sunday,

            rr.subject_area,
            rr.module_type,
            rr.title,
            rr.administered_at,

            case
                when rr.is_mastery then 1 when not rr.is_mastery then 0
            end as is_mastery_int,
            row_number() over (
                partition by
                    rr.powerschool_student_number,
                    rr.academic_year,
                    rr.subject_area,
                    sw.week_start_monday
                order by sw.week_start_monday desc
            ) as rn_week_latest,
        from student_weeks as sw
        left join
            {{ ref("int_assessments__response_rollup") }} as rr
            on sw.powerschool_student_number = rr.powerschool_school_id
            and sw.academic_year = rr.academic_year
            and rr.administered_at between sw.week_start_monday and sw.week_end_sunday
        where
            (rr.response_type = 'overall' or rr.response_type is null)
            and rr.module_type in ('QA', 'MQQ')
    )

select
    powerschool_student_number,
    academic_year,
    subject_area,
    module_type,
    title,
    administered_at,
    week_start_monday,
    week_end_sunday,
    is_mastery_int,

    last_value(is_mastery_int ignore nulls) over (
        partition by powerschool_student_number, subject_area, academic_year
        order by week_start_monday
        rows between unbounded preceding and current row
    ) as mastery_as_of_week,
from assessment_weeks
where rn_week_latest = 1
