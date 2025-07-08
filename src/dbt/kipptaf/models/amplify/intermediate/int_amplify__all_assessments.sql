with
    assessments_scores as (
        -- benchmark scores
        select
            bss.academic_year,
            bss.student_primary_id as student_number,
            bss.assessment_grade,
            bss.assessment_grade_int,
            bss.benchmark_period as period,
            bss.client_date,
            bss.sync_date,

            u.measure_name,
            u.measure_name_code,
            u.measure_standard,
            u.measure_standard_score,
            u.measure_standard_level,
            u.measure_standard_level_int,
            u.measure_percentile,
            u.measure_semester_growth,
            u.measure_year_growth,

            'Benchmark' as assessment_type,
            null as probe_number,
            null as total_number_of_probes,
            null as score_change,

            case
                bss.school_name
                when 'KIPP BOLD Academy'
                then 'Newark'
                when 'KIPP Courage Academy'
                then 'Miami'
                when 'KIPP Hatch (Camden, NJ)'
                then 'Camden'
                when 'KIPP Justice Academy'
                then 'Newark'
                when 'KIPP Lanning Square Middle'
                then 'Camden'
                when 'KIPP Lanning Square Primary (Camden, NJ)'
                then 'Camden'
                when 'KIPP Life Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Purpose Academy'
                then 'Newark'
                when 'KIPP Rise Academy'
                then 'Newark'
                when 'KIPP Royalty Academy (Mia)'
                then 'Miami'
                when 'KIPP SPARK (Newark, NJ)'
                then 'Newark'
                when 'KIPP Seek Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Sumner Elementary (Camden, NJ)'
                then 'Camden'
                when 'KIPP TEAM Academy'
                then 'Newark'
                when 'KIPP THRIVE (Newark, NJ)'
                then 'Newark'
                when 'KIPP Truth Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Upper Roseville Academy (Newark, NJ)'
                then 'Newark'
            end as region,

            row_number() over (
                partition by u.surrogate_key, u.measure_standard
                order by u.measure_standard_level_int desc
            ) as rn_highest,

            row_number() over (
                partition by bss.academic_year, bss.student_primary_id
                order by bss.client_date
            ) as rn_distinct,

        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        where
            bss.academic_year >= 2023
            and bss.enrollment_grade = bss.assessment_grade
            and bss.assessment_grade is not null

        union all

        -- 7/8 benchmark scores SY24 only
        select
            df.academic_year as academic_year,
            df.student_id as student_number,
            df.assessment_grade,
            df.assessment_grade_int,

            df.period,
            df.`date` as client_date,
            df.`date` as sync_date,

            df.measure_name,
            df.measure_name_code,
            df.measure_standard,
            df.measure_standard_score,
            df.measure_standard_level,
            df.measure_standard_level_int,
            df.measure_percentile,

            cast(null as string) as measure_semester_growth,
            cast(null as string) as measure_year_growth,
            'Benchmark' as assessment_type,
            null as probe_number,
            null as total_number_of_probes,
            null as score_change,

            x.region,

            row_number() over (
                partition by df.surrogate_key, df.measure_standard
                order by df.measure_standard_level_int desc
            ) as rn_highest,

            row_number() over (
                partition by df.academic_year, df.student_id order by df.`date`
            ) as rn_distinct,

        from {{ ref("int_amplify__dibels_data_farming_unpivot") }} as df
        left join
            {{ ref("stg_google_sheets__dibels_df_student_xwalk") }} as x
            on df.student_id = x.student_number
            and df.period = x.admin_season
        where
            df.measure_standard
            in ('Reading Fluency (ORF)', 'Reading Comprehension (Maze)', 'Composite')

        union all

        -- pm scores
        select
            p.academic_year,
            p.student_primary_id as student_number,
            p.assessment_grade,
            p.assessment_grade_int,
            p.pm_period as period,
            p.client_date,
            p.sync_date,
            p.measure_name,
            p.measure_name_code,
            p.measure as measure_standard,
            p.measure_standard_score,

            'NA' as measure_standard_level,

            null as measure_standard_level_int,
            null as measure_percentile,

            'NA' as measure_semester_growth,
            'NA' as measure_year_growth,
            'PM' as assessment_type,

            p.probe_number,
            p.total_number_of_probes,
            p.measure_standard_score_change,

            case
                p.school_name
                when 'KIPP BOLD Academy'
                then 'Newark'
                when 'KIPP Courage Academy'
                then 'Miami'
                when 'KIPP Hatch (Camden, NJ)'
                then 'Camden'
                when 'KIPP Justice Academy'
                then 'Newark'
                when 'KIPP Lanning Square Middle'
                then 'Camden'
                when 'KIPP Lanning Square Primary (Camden, NJ)'
                then 'Camden'
                when 'KIPP Life Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Purpose Academy'
                then 'Newark'
                when 'KIPP Rise Academy'
                then 'Newark'
                when 'KIPP Royalty Academy (Mia)'
                then 'Miami'
                when 'KIPP SPARK (Newark, NJ)'
                then 'Newark'
                when 'KIPP Seek Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Sumner Elementary (Camden, NJ)'
                then 'Camden'
                when 'KIPP TEAM Academy'
                then 'Newark'
                when 'KIPP THRIVE (Newark, NJ)'
                then 'Newark'
                when 'KIPP Truth Academy (Newark, NJ)'
                then 'Newark'
                when 'KIPP Upper Roseville Academy (Newark, NJ)'
                then 'Newark'
            end as region,

            row_number() over (
                partition by p.surrogate_key, p.measure, a.pm_round
                order by p.measure_standard_score desc
            ) as rn_highest,

            row_number() over (
                partition by p.academic_year, p.student_primary_id
                order by p.client_date
            ) as rn_distinct,

        from {{ ref("stg_amplify__pm_student_summary") }} as p
        inner join
            {{ ref("stg_google_sheets__dibels_pm_expectations") }} as a
            on p.academic_year = a.academic_year
            and p.region = a.region
            and p.assessment_grade_int = a.grade_level
            and p.measure = a.measure_standard
            and p.client_date between a.start_date and a.end_date
        where
            p.academic_year >= 2023
            and p.enrollment_grade = p.assessment_grade
            and p.assessment_grade is not null
    ),

    composite_only as (
        select academic_year, student_number, period, measure_standard_level,
        from assessments_scores
        where measure_standard = 'Composite' and rn_highest = 1
    ),

    overall_composite_by_window as (
        select
            academic_year,
            student_number,

            coalesce(p.boy, 'No data') as boy,
            coalesce(p.moy, 'No data') as moy,
            coalesce(p.eoy, 'No data') as eoy,
        from
            composite_only
            pivot (max(measure_standard_level) for period in ('BOY', 'MOY', 'EOY')) as p
    ),

    probe_eligible_tag as (
        select
            s.academic_year,
            s.student_number,

            c.boy,
            c.moy,
            c.eoy,

            if(
                c.boy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as boy_probe_eligible,

            if(
                c.moy in ('Below Benchmark', 'Well Below Benchmark'), 'Yes', 'No'
            ) as moy_probe_eligible,

        from assessments_scores as s
        left join
            overall_composite_by_window as c
            on s.academic_year = c.academic_year
            and s.student_number = c.student_number
        where s.rn_distinct = 1 and s.assessment_type = 'Benchmark'
    )

select
    s.academic_year,
    s.region,
    s.student_number,
    s.assessment_type,
    s.assessment_grade,
    s.assessment_grade_int,
    s.period,
    s.client_date,
    s.sync_date,
    s.measure_name,
    s.measure_name_code,
    s.measure_standard,
    s.measure_standard_score,
    s.measure_standard_level,
    s.measure_standard_level_int,
    s.measure_percentile,
    s.measure_semester_growth,
    s.measure_year_growth,
    s.probe_number,
    s.total_number_of_probes,
    s.score_change,

    p.boy_probe_eligible,
    p.moy_probe_eligible,
    p.boy as boy_composite,
    p.moy as moy_composite,
    p.eoy as eoy_composite,

    case
        when s.measure_standard_level_int >= 3
        then 'At/Above'
        when s.measure_standard_level_int <= 2
        then 'Below/Well Below'
    end as aggregated_measure_standard_level,

from assessments_scores as s
left join
    probe_eligible_tag as p
    on s.academic_year = p.academic_year
    and s.student_number = p.student_number
where s.assessment_type = 'Benchmark' and s.rn_highest = 1

union all

select
    s.academic_year,
    s.region,
    s.student_number,
    s.assessment_type,
    s.assessment_grade,
    s.assessment_grade_int,
    s.period,
    s.client_date,
    s.sync_date,
    s.measure_name,
    s.measure_name_code,
    s.measure_standard,
    s.measure_standard_score,
    s.measure_standard_level,
    s.measure_standard_level_int,
    s.measure_percentile,
    s.measure_semester_growth,
    s.measure_year_growth,
    s.probe_number,
    s.total_number_of_probes,
    s.score_change,

    p.boy_probe_eligible,
    p.moy_probe_eligible,
    p.boy as boy_composite,
    p.moy as moy_composite,
    p.eoy as eoy_composite,

    case
        when s.measure_standard_level_int >= 3
        then 'At/Above'
        when s.measure_standard_level_int <= 2
        then 'Below/Well Below'
    end as aggregated_measure_standard_level,

from assessments_scores as s
left join
    probe_eligible_tag as p
    on s.academic_year = p.academic_year
    and s.student_number = p.student_number
where s.assessment_type = 'PM' and s.rn_highest = 1
