with
    schedule_candidates as (
        select
            students_student_number as student_number,
            cc_academic_year as academic_year,
            cc_termid,
            cc_dateenrolled,
            cc_dateleft,
            cc_sectionid,
            courses_course_name,
            teacher_lastfirst,

            if(
                courses_credittype = 'HR',
                sections_section_number,
                sections_external_expression
            ) as schedule_section,

            case
                when
                    courses_course_name like 'College and Career%' or discipline = 'CCR'
                then 'CCR'
                when cc_course_number = 'SEM22106G1'
                then 'Advisory'
                when courses_credittype = 'HR'
                then 'Homeroom'
            end as schedule_source,

        from {{ ref("base_powerschool__course_enrollments") }}
        where not is_dropped_section
    ),

    ranked as (
        select
            student_number,
            academic_year,
            courses_course_name,
            teacher_lastfirst,
            schedule_section,
            schedule_source,

            row_number() over (
                partition by student_number, academic_year
                order by
                    case
                        schedule_source when 'CCR' then 1 when 'Advisory' then 2 else 3
                    end,
                    cc_termid desc,
                    cc_dateenrolled desc,
                    cc_dateleft desc,
                    cc_sectionid asc
            ) as rn_schedule,

        from schedule_candidates
        where schedule_source is not null
    )

select
    student_number,
    academic_year,
    courses_course_name as ccr_course,
    teacher_lastfirst as ccr_teacher_name,
    schedule_section as ccr_section,
    schedule_source as ccr_course_source,

from ranked
where rn_schedule = 1
