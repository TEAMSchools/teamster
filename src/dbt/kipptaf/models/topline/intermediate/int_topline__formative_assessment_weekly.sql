with
    responses_discipline as (
        select
            powerschool_student_number,
            academic_year,
            module_type,
            title,
            administered_at,
            discipline,

            case
                when is_mastery then 1 when not is_mastery then 0 else -1
            end as is_mastery_int,
        from {{ ref("int_assessments__response_rollup") }}
        where
            response_type = 'overall'
            and module_type in ('QA', 'MQQ', 'CRQ')
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    assessment_weeks as (
        select
            sw.student_number,
            sw.academic_year,
            sw.week_start_monday,
            sw.week_end_sunday,
            sw.discipline,

            rr.title,
            rr.administered_at,
            rr.is_mastery_int,

            case
                when rr.module_type in ('QA', 'MQQ')
                then 'All'
                when rr.module_type = 'CRQ' and sw.region = 'Miami'
                then 'Florida'
            end as formative_strategy,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as sw
        left join
            responses_discipline as rr
            on sw.student_number = rr.powerschool_student_number
            and sw.academic_year = rr.academic_year
            and sw.discipline = rr.discipline
            and rr.administered_at between sw.week_start_monday and sw.week_end_sunday
        where
            sw.is_enrolled_week
            and sw.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    assessment_weeks_ranked as (
        select
            student_number,
            academic_year,
            week_start_monday,
            week_end_sunday,
            discipline,
            formative_strategy,
            is_mastery_int,

            row_number() over (
                partition by
                    student_number,
                    academic_year,
                    week_start_monday,
                    discipline,
                    formative_strategy
                order by administered_at desc, title desc
            ) as rn,
        from assessment_weeks
        where formative_strategy is not null
    )

select
    student_number,
    academic_year,
    week_start_monday,
    week_end_sunday,
    discipline,
    formative_strategy,

    if(is_mastery_int = -1, null, is_mastery_int) as is_mastery_running_int,
from assessment_weeks_ranked
where rn = 1
