with
    -- the two expectation gates appended. expected_row_count is computed in the
    -- gates themselves, where the cohort partition lives next to the column that
    -- causes it.
    expected_tests as (
        select
            academic_year,
            region,
            grade,
            assessment_type,
            admin_season,
            round_number,
            `start_date`,
            end_date,
            expected_row_count,

            -- 'BM' rather than 'Benchmark', so this joins
            -- int_amplify__all_assessments model_type directly
            if(assessment_type = 'PM', 'Internal', 'BM') as model_type,

            -- see student_expectations below. Benchmark is not eligibility-gated,
            -- so it takes a sentinel every student carries; the internal method
            -- wants only probe-eligible students.
            if(assessment_type = 'PM', 'Yes', 'All') as eligibility_key,

        from {{ ref("int_google_sheets__dibels_expected_assessments") }}
        where assessment_include is null and pm_goal_include is null

        union all

        select
            academic_year,
            region,
            grade,
            assessment_type,
            admin_season,
            round_number,
            `start_date`,
            end_date,
            expected_row_count,

            'Aimline' as model_type,

            -- aimline matches a cohort rather than a flag
            measure_standard_level as eligibility_key,

        from {{ ref("int_google_sheets__dibels__expected_assessments_by_levels") }}
        where assessment_include is null and pm_goal_include is null
    ),

    students as (
        select
            academic_year,
            region,
            student_number,
            enroll_status,
            grade_level,
            entrydate,
            exitdate,
            boy_probe_eligible,
            moy_probe_eligible,
            dibels_boy_composite,
            dibels_moy_composite,

        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where discipline = 'ELA' and enroll_status in (0, 2, 3) and grade_level <= 8
    ),

    -- one row per student per (model, season) they could owe testing for, each
    -- carrying that combination's own eligibility value. This is what lets three
    -- different eligibility rules -- none for Benchmark, a probe-eligible flag
    -- for internal, a cohort match for aimline -- resolve to one equality
    -- against expected_tests rather than three UNION branches.
    student_expectations as (
        select
            s.academic_year,
            s.region,
            s.student_number,
            s.enroll_status,
            s.grade_level,
            s.entrydate,
            s.exitdate,

            k.admin_season,
            k.model_type,
            k.eligibility_key,

        from students as s
        cross join
            unnest(
                [
                    struct(
                        'BOY' as admin_season,
                        'BM' as model_type,
                        'All' as eligibility_key
                    ),
                    ('MOY', 'BM', 'All'),
                    ('EOY', 'BM', 'All'),
                    ('BOY->MOY', 'Internal', s.boy_probe_eligible),
                    ('MOY->EOY', 'Internal', s.moy_probe_eligible),
                    ('BOY->MOY', 'Aimline', s.dibels_boy_composite),
                    ('MOY->EOY', 'Aimline', s.dibels_moy_composite)
                ]
            ) as k
    ),

    roster_enrollment_dates as (
        select
            e.academic_year,
            e.region,
            e.assessment_type,
            e.model_type,
            e.admin_season,
            e.round_number,
            e.expected_row_count,

            s.student_number,
            s.enroll_status,
            s.grade_level,

            coalesce(a.actual_row_count, 0) as actual_row_count,

            -- the composite fallbacks only ever fire on a Benchmark row, since a
            -- PM row's admin_season is BOY->MOY or MOY->EOY. A student can hold a
            -- composite without having sat every measure, and that still counts
            -- as completing the benchmark round.
            case
                when e.expected_row_count = a.actual_row_count
                then true
                when e.admin_season = 'BOY' and a.boy_composite != 'No data'
                then true
                when e.admin_season = 'MOY' and a.moy_composite != 'No data'
                then true
                when e.admin_season = 'EOY' and a.eoy_composite != 'No data'
                then true
                else false
            end as completed_test_round,

            row_number() over (
                partition by
                    e.academic_year,
                    e.region,
                    e.model_type,
                    e.admin_season,
                    e.round_number,
                    s.student_number,
                    s.grade_level
            ) as rn,

        from expected_tests as e
        inner join
            student_expectations as s
            on e.academic_year = s.academic_year
            and e.region = s.region
            and e.grade = s.grade_level
            and e.admin_season = s.admin_season
            and e.model_type = s.model_type
            -- At/Above Benchmark and 'No Test' match no by-levels row, and a
            -- student who is not probe-eligible matches no internal PM row. Both
            -- are the intended outcome.
            and e.eligibility_key = s.eligibility_key
            and (
                e.start_date between s.entrydate and s.exitdate
                or e.end_date between s.entrydate and s.exitdate
            )
        left join
            {{ ref("int_amplify__all_assessments") }} as a
            on e.admin_season = a.period
            and e.round_number = a.round_number
            and e.model_type = a.model_type
            and s.academic_year = a.academic_year
            and s.region = a.region
            and s.student_number = a.student_number
            and s.grade_level = a.assessment_grade_int
    )

select
    academic_year,
    region,
    student_number,
    grade_level,
    enroll_status,
    assessment_type,
    model_type,
    admin_season,
    round_number,
    expected_row_count,
    actual_row_count,
    completed_test_round,

    case
        when assessment_type = 'Benchmark'
        then 'Combo'
        when model_type = 'Internal' and grade_level <= 2
        then 'Combo'
        when model_type = 'Aimline' and grade_level >= 3
        then 'Combo'
        else 'Not Combo'
    end as participation_group,

    if(completed_test_round, 1, 0) as completed_test_round_int,

from roster_enrollment_dates
where rn = 1
