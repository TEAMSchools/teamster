with
    students as (
        select
            academic_year,
            region,
            student_number,
            grade_level,
            entrydate,
            exitdate,

            if(
                dibels_boy_composite in ('Below Benchmark', 'Well Below Benchmark'),
                'Yes',
                'No'
            ) as boy_probe_eligible,

            if(
                dibels_moy_composite in ('Below Benchmark', 'Well Below Benchmark'),
                'Yes',
                'No'
            ) as moy_probe_eligible,

        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where
            enroll_status != -1
            and grade_level <= 8
            and academic_year >= 2023
            and discipline = 'ELA'
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

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            true as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and e.assessment_type = 'Benchmark'
            and e.start_date between s.entrydate and s.exitdate
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and e.admin_season = a.period
            and e.`round` = a.`round`

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            true as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and s.boy_probe_eligible = 'Yes'
            and e.admin_season = 'BOY->MOY'
            and e.start_date between s.entrydate and s.exitdate
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.boy_probe_eligible = a.boy_probe_eligible
            and e.admin_season = a.period
            and e.`round` = a.`round`

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            true as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and s.moy_probe_eligible = 'Yes'
            and e.admin_season = 'MOY->EOY'
            and e.start_date between s.entrydate and s.exitdate
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.moy_probe_eligible = a.moy_probe_eligible
            and e.admin_season = a.period
            and e.`round` = a.`round`
    ),

    roster_no_enrollment_dates as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            false as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and e.assessment_type = 'Benchmark'
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and e.admin_season = a.period
            and e.`round` = a.`round`

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            false as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and s.boy_probe_eligible = 'Yes'
            and e.admin_season = 'BOY->MOY'
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.boy_probe_eligible = a.boy_probe_eligible
            and e.admin_season = a.period
            and e.`round` = a.`round`

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.`round`,
            e.expected_row_count,

            false as enrollment_dates_account,

            coalesce(a.actual_row_count, 0) as actual_row_count,

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
            and s.moy_probe_eligible = 'Yes'
            and e.admin_season = 'MOY->EOY'
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.moy_probe_eligible = a.moy_probe_eligible
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
