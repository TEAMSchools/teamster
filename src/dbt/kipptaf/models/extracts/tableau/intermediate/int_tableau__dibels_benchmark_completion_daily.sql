with
    expectations as (
        select
            academic_year,
            region,
            assessment_type,
            admin_season,
            expected_measure_standard,
            grade,
            `start_date`,
            end_date,
            round_number,

            count(*) over (
                partition by academic_year, region, grade, admin_season, round_number
            ) as expected_measure_count,

        from {{ ref("int_google_sheets__dibels_expected_assessments") }}
        where assessment_include is null and pm_goal_include is null
    ),

    students as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            schoolid,
            school,
            entrydate,
            exitdate,

            coalesce(advisory, 'Unassigned') as advisory,

        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where discipline = 'ELA' and enroll_status in (0, 2, 3) and grade_level <= 8
    ),

    student_measures as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.school,
            s.advisory,

            e.assessment_type,
            e.admin_season,
            e.expected_measure_standard,
            e.round_number,
            e.`start_date`,
            e.end_date,
            e.expected_measure_count,

        from students as s
        inner join
            expectations as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and (
                e.`start_date` between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
    ),

    spine as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            schoolid,
            school,
            advisory,
            assessment_type,
            admin_season,
            expected_measure_standard,
            round_number,
            `start_date`,
            end_date,
            expected_measure_count,

            calendar_day,

        from student_measures
        cross join
            unnest(
                generate_date_array(`start_date`, end_date, interval 1 day)
            ) as calendar_day
    ),

    base as (
        select
            academic_year,
            region,
            student_number,
            assessment_type,
            assessment_grade_int,
            `period`,
            round_number,
            client_date,
            measure_standard,

        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'Benchmark'

        union all

        select
            academic_year,
            region,
            student_number,
            assessment_type,
            assessment_grade_int,
            `period`,
            round_number,
            client_date,
            measure_standard,

        from {{ ref("int_amplify__all_assessments") }}
        where assessment_type = 'PM' and overall_probe_eligible = 'Yes'
    ),

    joined as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.schoolid,
            s.school,
            s.advisory,
            s.assessment_type,
            s.admin_season,
            s.expected_measure_standard,
            s.round_number,
            s.`start_date`,
            s.end_date,
            s.expected_measure_count,
            s.calendar_day,

            b.client_date,

            coalesce(b.client_date <= s.calendar_day, false) as finished_measure,
            coalesce(b.client_date = s.calendar_day, false) as finished_this_day,

        from spine as s
        left join
            base as b
            on s.academic_year = b.academic_year
            and s.region = b.region
            and s.student_number = b.student_number
            and s.assessment_type = b.assessment_type
            and s.admin_season = b.`period`
            and s.round_number = b.round_number
            and s.expected_measure_standard = b.measure_standard
            and s.grade_level = b.assessment_grade_int
        where s.academic_year = {{ var("current_academic_year") }}
    ),

    rolled as (
        select
            *,

            sum(if(finished_measure, 1, 0)) over (
                partition by
                    academic_year,
                    region,
                    assessment_type,
                    student_number,
                    admin_season,
                    round_number,
                    calendar_day
            ) as measures_finished_to_date,

        from joined
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
    admin_season as `period`,
    expected_measure_standard,
    round_number,
    `start_date`,
    end_date,
    expected_measure_count,
    calendar_day,
    client_date,
    finished_measure,
    finished_this_day,
    measures_finished_to_date,

    if(
        measures_finished_to_date = expected_measure_count, true, false
    ) as finished_round,

from rolled
