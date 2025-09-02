with
    students as (
        select
            academic_year,
            region,
            student_number,
            enroll_status,
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
        where discipline = 'ELA' and enroll_status in (0, 2, 3) and grade_level <= 8
    ),

    expected_tests as (
        select
            academic_year,
            region,
            grade,
            assessment_type,
            admin_season,
            round_number,
            start_date,
            end_date,

            count(*) over (
                partition by academic_year, region, grade, admin_season, round_number
            ) as expected_row_count,

        from {{ ref("int_google_sheets__dibels_expected_assessments") }}
        where assessment_include is null and pm_goal_include is null
    ),

    roster_enrollment_dates as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.enroll_status,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.round_number,
            e.expected_row_count,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            case
                when e.expected_row_count = a.actual_row_count
                then true
                when e.admin_season = 'BOY' and a.boy_composite != 'No Data'
                then true
                when e.admin_season = 'MOY' and a.moy_composite != 'No Data'
                then true
                when e.admin_season = 'EOY' and a.eoy_composite != 'No Data'
                then true
                else false
            end as completed_test_round,

            row_number() over (
                partition by
                    s.academic_year,
                    s.region,
                    s.student_number,
                    s.grade_level,
                    e.admin_season,
                    e.round_number
            ) as rn,

        from students as s
        inner join
            expected_tests as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and e.assessment_type = 'Benchmark'
            and (
                e.start_date between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and e.admin_season = a.period
            and e.round_number = a.round_number

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.enroll_status,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.round_number,
            e.expected_row_count,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            if(
                e.expected_row_count = a.actual_row_count, true, false
            ) as completed_test_round,

            row_number() over (
                partition by
                    s.academic_year,
                    s.region,
                    s.student_number,
                    s.grade_level,
                    e.admin_season,
                    e.round_number
            ) as rn,

        from students as s
        inner join
            expected_tests as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and (
                e.start_date between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
            and e.admin_season = 'BOY->MOY'
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.boy_probe_eligible = a.boy_probe_eligible
            and e.admin_season = a.period
            and e.round_number = a.round_number
        where s.boy_probe_eligible = 'Yes'

        union all

        select
            s.academic_year,
            s.region,
            s.student_number,
            s.enroll_status,
            s.grade_level,

            e.assessment_type,
            e.admin_season,
            e.round_number,
            e.expected_row_count,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            if(
                e.expected_row_count = a.actual_row_count, true, false
            ) as completed_test_round,

            row_number() over (
                partition by
                    s.academic_year,
                    s.region,
                    s.student_number,
                    s.grade_level,
                    e.admin_season,
                    e.round_number
            ) as rn,

        from students as s
        inner join
            expected_tests as e
            on s.academic_year = e.academic_year
            and s.region = e.region
            and s.grade_level = e.grade
            and (
                e.start_date between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
            and e.admin_season = 'MOY->EOY'
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
            and s.moy_probe_eligible = a.moy_probe_eligible
            and e.admin_season = a.period
            and e.round_number = a.round_number
        where s.moy_probe_eligible = 'Yes'
    )

select
    academic_year,
    region,
    student_number,
    grade_level,
    enroll_status,
    assessment_type,
    admin_season,
    round_number,
    expected_row_count,
    actual_row_count,
    completed_test_round,
    if(completed_test_round, 1, 0) as completed_test_round_int,

from roster_enrollment_dates
where rn = 1
