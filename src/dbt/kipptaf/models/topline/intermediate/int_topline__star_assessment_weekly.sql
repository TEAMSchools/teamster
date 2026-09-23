with
    subject_weeks as (
        select
            student_number,
            academic_year,
            region,
            grade_level,
            week_start_monday,
            week_end_sunday,
            discipline,
            entrydate,
            is_enrolled_week,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }}
        where
            region = 'Miami' and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    subject_weeks_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="subject_weeks",
                partition_by="student_number, academic_year, week_start_monday, discipline",
                order_by="is_enrolled_week desc, entrydate desc",
            )
        }}
    ),

    star_results as (
        select
            student_display_id,
            academic_year,
            star_discipline,
            star_subject,
            screening_period_window_name,
            completed_date_value,
            is_state_benchmark_proficient_int,
        from {{ ref("stg_renlearn__star") }}
        where
            rn_subject_round = 1
            and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    star_results_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="star_results",
                partition_by="student_display_id, academic_year, star_discipline, screening_period_window_name",
                order_by="completed_date_value desc, (star_subject = 'Reading') desc",
            )
        }}
    )

select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    s.is_state_benchmark_proficient_int,
from subject_weeks_deduplicate as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'ST'
inner join
    star_results_deduplicate as s
    on cw.student_number = s.student_display_id
    and cw.academic_year = s.academic_year
    and cw.discipline = s.star_discipline
    and rt.name = s.screening_period_window_name
where cw.grade_level <= 2
