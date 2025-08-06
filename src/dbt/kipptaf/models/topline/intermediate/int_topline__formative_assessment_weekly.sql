with
    subject_discipline_crosswalk as (
        select illuminate_subject_area, discipline,
        from {{ ref("stg_assessments__course_subject_crosswalk") }}
        group by illuminate_subject_area, discipline
    ),

    responses_discipline as (
        select rr.*, cx.discipline,
        from {{ ref("int_assessments__response_rollup") }} as rr
        inner join
            subject_discipline_crosswalk as cx
            on rr.subject_area = cx.illuminate_subject_area
    ),

    assessment_weeks as (
        select
            sw.student_number,
            sw.academic_year,
            sw.week_start_monday,
            sw.week_end_sunday,

            rr.subject_area,
            rr.discipline,
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
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as sw
        left join
            responses_discipline as rr
            on sw.student_number = rr.powerschool_student_number
            and sw.academic_year = rr.academic_year
            and sw.discipline = rr.discipline
            and rr.administered_at between sw.week_start_monday and sw.week_end_sunday
        where
            (rr.response_type = 'overall' or rr.response_type is null)
            and rr.module_type in ('QA', 'MQQ')
    )

select
    student_number,
    academic_year,
    subject_area,
    discipline,
    module_type,
    title,
    administered_at,
    week_start_monday,
    week_end_sunday,
    is_mastery_int,

    last_value(is_mastery_int ignore nulls) over (
        partition by student_number, discipline, academic_year
        order by week_start_monday
        rows between unbounded preceding and current row
    ) as mastery_as_of_week,
from assessment_weeks
where rn_week_latest = 1
