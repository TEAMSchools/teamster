with
    daily as (
        select
            academic_year,
            region,
            schoolid,
            school,
            grade_level,
            advisory,
            assessment_type,
            `period`,
            round_number,
            `start_date`,
            end_date,
            calendar_day,
            student_number,
            finished_measure,
            finished_this_day,

            if(finished_round, student_number, null) as finished_round_student_number,

        from {{ ref("int_tableau__dibels_benchmark_completion_daily") }}
        where
            region = 'Camden'
            and not is_self_contained
            and not is_out_of_district
            and calendar_day <= current_date('{{ var("local_timezone") }}')
    )

select
    academic_year,
    region,
    schoolid,
    school,
    grade_level,
    advisory,
    assessment_type,
    `period`,
    round_number,
    `start_date`,
    end_date,
    calendar_day,

    count(distinct student_number) as students_expected,
    count(*) as measures_expected,
    countif(finished_measure) as measures_finished,
    countif(finished_this_day) as measures_finished_this_day,
    count(distinct finished_round_student_number) as students_finished_round,

    round(
        safe_divide(countif(finished_measure), count(*)), 4
    ) as measure_completion_rate,

    round(
        safe_divide(
            count(distinct finished_round_student_number),
            count(distinct student_number)
        ),
        4
    ) as student_completion_rate,

from daily
group by
    academic_year,
    region,
    schoolid,
    school,
    grade_level,
    advisory,
    assessment_type,
    `period`,
    round_number,
    `start_date`,
    end_date,
    calendar_day
