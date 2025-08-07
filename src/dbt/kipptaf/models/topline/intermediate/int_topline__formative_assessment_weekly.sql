with

    responses_discipline as (
        select
            powerschool_student_number,
            academic_year,
            response_type,
            subject_area,
            module_type,
            title,
            administered_at,
            is_mastery,
            discipline,

            case
                when is_mastery then 1 when not is_mastery then 0 else -1
            end as is_mastery_int,
        from {{ ref("int_assessments__response_rollup") }}
        where response_type = 'overall' and module_type in ('QA', 'MQQ')
    ),

    assessment_weeks as (
        select
            sw.student_number,
            sw.academic_year,
            sw.week_start_monday,
            sw.week_end_sunday,
            sw.discipline,

            rr.subject_area,
            rr.module_type,
            rr.title,
            rr.administered_at,
            rr.is_mastery,
            rr.is_mastery_int,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as sw
        left join
            responses_discipline as rr
            on sw.student_number = rr.powerschool_student_number
            and sw.academic_year = rr.academic_year
            and sw.discipline = rr.discipline
            and rr.administered_at between sw.week_start_monday and sw.week_end_sunday
    ),

    calcs as (
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
                order by week_start_monday asc
            ) as mastery_as_of_week,
        from assessment_weeks
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
    mastery_as_of_week,

    if(mastery_as_of_week = -1, null, mastery_as_of_week) as is_mastery_running_int,
from calcs
