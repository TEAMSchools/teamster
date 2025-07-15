with
    students as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            enroll_status,
            entrydate,
            exitdate
        from {{ ref("int_extracts__student_enrollments") }}
        where enroll_status != -1 and grade_level <= 8 and academic_year >= 2023
    ),

    expected_tests as (
        select
            e.academic_year,
            e.region,
            e.grade,
            e.assessment_type,
            e.admin_season,
            e.`round`,

            t.start_date,
            t.end_date,

            count(*) over (
                partition by
                    e.academic_year, e.region, e.grade, e.admin_season, e.`round`
            ) as expected_row_count,

        from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as e
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on e.academic_year = t.academic_year
            and e.region = t.region
            and e.admin_season = t.name
            and e.test_code = t.code
            and t.type = 'LIT'
        where e.assessment_include is null
    ),

    roster_enrollment_dates as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.enroll_status,
            s.entrydate,
            s.exitdate,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            true as enrollment_dates_account,

            if(
                e.expected_row_count = a.actual_row_count, true, false
            ) as completed_test_round,

            if(
                e.expected_row_count = a.actual_row_count, 1, 0
            ) as completed_test_round_int,

            row_number() over (
                partition by
                    s.academic_year,
                    s.region,
                    s.student_number,
                    s.grade_level,
                    e.admin_season,
                    e.`round`
            ) as rn,

        from students as s
        inner join
            expected_tests as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and s.entrydate between e.start_date and e.end_date
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and e.admin_season = a.period
            and e.`round` = a.`round`
    ),

    roster_no_enrollment_dates as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,
            s.enroll_status,
            s.entrydate,
            s.exitdate,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            false as enrollment_dates_account,

            if(
                e.expected_row_count = a.actual_row_count, true, false
            ) as completed_test_round,

            if(
                e.expected_row_count = a.actual_row_count, 1, 0
            ) as completed_test_round_int,

            row_number() over (
                partition by
                    s.academic_year,
                    s.region,
                    s.student_number,
                    s.grade_level,
                    e.admin_season,
                    e.`round`
            ) as rn,

        from students as s
        inner join
            expected_tests as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and e.admin_season = a.period
            and e.`round` = a.`round`
    )

select
    academic_year,
    region,
    student_number,
    grade_level,
    enrollment_dates_account,
    assessment_type,
    admin_season,
    `round`,
    expected_row_count,
    actual_row_count,
    completed_test_round,
    completed_test_round_int,

from roster_enrollment_dates
where rn = 1

union all

select
    academic_year,
    region,
    student_number,
    grade_level,
    enrollment_dates_account,
    assessment_type,
    admin_season,
    `round`,
    expected_row_count,
    actual_row_count,
    completed_test_round,
    completed_test_round_int,

from roster_no_enrollment_dates
where rn = 1
