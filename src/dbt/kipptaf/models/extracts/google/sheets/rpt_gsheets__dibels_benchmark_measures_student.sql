with
    outstanding as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            schoolid,
            school,
            advisory,
            assessment_type,
            `period`,
            round_number,
            `start_date`,
            end_date,
            expected_measure_standard,
            expected_measure_count,
            calendar_day,
            measures_finished_to_date,

        from {{ ref("int_tableau__dibels_benchmark_completion_daily") }}
        where
            region = 'Camden'
            and not finished_measure
            and not is_self_contained
            and not is_out_of_district
            and calendar_day <= current_date('{{ var("local_timezone") }}')
    )

select
    academic_year,
    region,
    student_number,
    grade_level,
    schoolid,
    school,
    advisory,
    assessment_type,
    `period`,
    round_number,
    `start_date`,
    end_date,
    expected_measure_standard,
    expected_measure_count,
    calendar_day,
    measures_finished_to_date,

    expected_measure_count - measures_finished_to_date as measures_outstanding,

from outstanding
