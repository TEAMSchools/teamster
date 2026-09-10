with
    -- grain projection, not dup-masking: measure_standard is joined, not
    -- projected, so a round's several measures collapse to one row
    pm_scores as (
        select
            r._dbt_source_project,
            r.academic_year,
            r.region,
            r.student_number,
            r.assessment_grade_int,
            r.boy_probe_eligible,
            r.moy_probe_eligible,
            r.boy_composite,
            r.moy_composite,
            r.eoy_composite,

            -- period is the PM season, not the benchmark that opened it -- the
            -- participation roster joins admin_season to it
            r.matching_season as `period`,
            r.overall_probe_eligible as pm_eligible,

            e.assessment_type,
            e.round_number,
            e.month_round,
            e.start_date,
            e.end_date,
            e.expected_measure_standard,

            p.assessment_grade,
            p.client_date,
            p.sync_date,
            p.surrogate_key,
            p.measure_name,
            p.measure_name_code,
            p.probe_number,
            p.total_number_of_probes,
            p.measure as measure_standard,
            p.measure_standard_score,

            cast(null as string) as aimline_status,
            cast(null as numeric) as goal,
            cast(null as int64) as met_aimline_goal,

            p.measure_standard_score_change as score_change,

            'Internal' as model_type,

            -- the benchmark season this round aims at, matching prod
            if(r.matching_season = 'BOY->MOY', 'MOY', 'EOY') as matching_season,

        from {{ ref("int_amplify__benchmark_student_summary") }} as r
        inner join
            {{ ref("int_google_sheets__dibels_expected_assessments") }} as e
            on r.academic_year = e.academic_year
            and r.region = e.region
            and r.assessment_grade_int = e.grade
            and r.matching_season = e.admin_season
            and e.assessment_include is null
            and e.pm_goal_include is null
        -- inner, not left: this model carries scored rows only, as it always
        -- has. An expected round with no score is the participation roster's
        -- job -- it counts the gate's rows against these.
        inner join
            {{ ref("int_amplify__mclass__pm_student_summary") }} as p
            on e.academic_year = p.academic_year
            and e.region = p.region
            and e.expected_measure_standard = p.measure
            and e.admin_season = p.pm_period
            and r.student_number = p.student_primary_id
            and p.client_date between e.start_date and e.end_date
        -- EOY opens no PM season. Year floor matches the aimline branch's
        -- coverage, so the two methods report over the same years.
        where
            r.period != 'EOY'
            and r.academic_year >= 2025
            and r.overall_probe_eligible = 'Yes'
            and r.rn_pm_eligibility = 1
            and p.enrollment_grade = p.assessment_grade
            and p.assessment_grade is not null

        union all

        select distinct
            r._dbt_source_project,
            r.academic_year,
            r.region,
            r.student_number,
            r.assessment_grade_int,
            r.boy_probe_eligible,
            r.moy_probe_eligible,
            r.boy_composite,
            r.moy_composite,
            r.eoy_composite,

            -- see the internal branch above
            r.matching_season as `period`,
            r.overall_aimline_composite_level as pm_eligible,

            e.assessment_type,
            e.round_number,
            e.month_round,
            e.start_date,
            e.end_date,
            e.expected_measure_standard,

            p.assessment_grade,
            p.device_date as client_date,
            p.sync_date,
            p.surrogate_key,
            p.measure_name,
            p.measure_name_code,
            p.probe_number,
            p.total_number_of_probes,
            p.measure as measure_standard,
            p.measure_standard_score,
            p.aimline_status,
            p.goal,

            case
                when p.aimline_status = 'At or Above'
                then 1
                when p.aimline_status = 'Below'
                then 0
            end as met_aimline_goal,

            -- the aimline source carries no score delta. Sits where branch 1's
            -- real column sits -- UNION ALL matches by position, not name.
            cast(null as numeric) as score_change,

            'Aimline' as model_type,

            if(r.matching_season = 'BOY->MOY', 'MOY', 'EOY') as matching_season,

        from {{ ref("int_amplify__benchmark_student_summary") }} as r
        inner join
            {{ ref("int_google_sheets__dibels__expected_assessments_by_levels") }} as e
            on r.academic_year = e.academic_year
            and r.region = e.region
            and r.assessment_grade_int = e.grade
            and r.matching_season = e.admin_season
            -- the cohort gate: At/Above matches no by-levels row
            and r.overall_aimline_composite_level = e.measure_standard_level
            and e.assessment_include is null
            and e.pm_goal_include is null
        -- see the internal branch above
        inner join
            {{ ref("int_amplify__mclass__pm_student_summary_aimline") }} as p
            on e.academic_year = p.academic_year
            and e.region = p.region
            and e.expected_measure_standard = p.measure
            and e.admin_season = p.pm_period
            and r.student_number = p.student_primary_id
            and p.device_date between e.start_date and e.end_date
        where
            r.period != 'EOY'
            and r.academic_year >= 2025
            and r.rn_pm_eligibility = 1
            and p.enrollment_grade = p.assessment_grade
            and p.assessment_grade is not null
    ),

    max_score as (
        select
            *,

            -- keeps a student's best score for a measure in a round, with the
            -- later probe winning a same-day tie. Deliberately NOT ordered by
            -- probe_number: that is Amplify's own numbering and does not align
            -- with our PM rounds. academic_year is load-bearing -- round numbers
            -- restart every year, so without it a student's AY2026 round 1
            -- competes with their AY2025 round 1 for the same measure and one
            -- real score is dropped. model_type keeps the two methods from
            -- ranking against each other. assessment_grade_int and period are
            -- here for the same reason as on rn_pm_eligibility below: each
            -- sitting is its own administration, so two grades in one round
            -- would otherwise collide and the lower score be dropped, silently.
            row_number() over (
                partition by
                    academic_year,
                    student_number,
                    model_type,
                    `period`,
                    assessment_grade_int,
                    round_number,
                    expected_measure_standard
                order by measure_standard_score desc, client_date desc
            ) as rn_highest,

        from pm_scores
    )

select
    academic_year,
    region,
    student_number,
    assessment_type,
    assessment_grade,
    assessment_grade_int,
    `period`,
    round_number,
    month_round,
    start_date,
    end_date,
    matching_season,
    client_date,
    sync_date,
    _dbt_source_project,
    measure_name,
    measure_name_code,
    measure_standard,
    measure_standard_score,
    measure_standard_level,
    measure_standard_level_int,
    measure_percentile,
    measure_semester_growth,
    measure_year_growth,

    -- PM-only columns, carried as nulls so the union lines up. Typed, because a
    -- bare null infers as INT64 and collides with the PM branch on score_change.
    cast(null as int64) as probe_number,
    cast(null as int64) as total_number_of_probes,
    cast(null as numeric) as score_change,
    cast(null as string) as aimline_status,
    cast(null as numeric) as goal,
    cast(null as int64) as met_aimline_goal,

    boy_probe_eligible,
    moy_probe_eligible,
    boy_composite,
    moy_composite,
    eoy_composite,

    model_type,

    'Text Study' as illuminate_subject,

    benchmark_goal_season,
    aggregated_measure_standard_level,
    foundation_measure_standard_level,
    overall_probe_eligible,
    actual_row_count,

from {{ ref("int_amplify__benchmark_student_summary") }}

union all

select
    s.academic_year,
    s.region,
    s.student_number,
    s.assessment_type,
    s.assessment_grade,
    s.assessment_grade_int,
    s.period,
    s.round_number,
    s.month_round,
    s.start_date,
    s.end_date,
    s.matching_season,
    s.client_date,
    s.sync_date,
    s._dbt_source_project,
    s.measure_name,
    s.measure_name_code,
    s.measure_standard,
    s.measure_standard_score,
    -- Benchmark-only concepts. PM carries no level, percentile or growth
    -- classification, and prod's PM branch set these same literals.
    'NA' as measure_standard_level,

    cast(null as int64) as measure_standard_level_int,
    cast(null as float64) as measure_percentile,

    'NA' as measure_semester_growth,
    'NA' as measure_year_growth,

    s.probe_number,
    s.total_number_of_probes,
    s.score_change,

    s.aimline_status,
    s.goal,
    s.met_aimline_goal,

    s.boy_probe_eligible,
    s.moy_probe_eligible,
    s.boy_composite,
    s.moy_composite,
    s.eoy_composite,

    s.model_type,

    'Text Study' as illuminate_subject,
    'NA' as benchmark_goal_season,

    -- Benchmark-only. PM carries no measure_standard_level_int, so prod's two
    -- case expressions returned null on every PM row; stated as null instead of
    -- branching on a column that is always null.
    cast(null as string) as aggregated_measure_standard_level,
    cast(null as string) as foundation_measure_standard_level,

    -- pm_eligible already resolved to this round's season. Position matters:
    -- UNION ALL binds by position and every column here is STRING, so a
    -- misplacement is accepted silently rather than failing on type.
    s.pm_eligible as overall_probe_eligible,

    -- model_type is in the partition so each method counts only its own rows.
    -- Without it the two methods count each other and a round that expects at
    -- most 5 measures reports up to 10, breaking every completion comparison.
    count(*) over (
        partition by
            s.academic_year,
            s.region,
            s.assessment_grade,
            s.period,
            s.round_number,
            s.student_number,
            s.model_type
    ) as actual_row_count,

from max_score as s
where s.rn_highest = 1
