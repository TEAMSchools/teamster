with
    assessments_scores as (
        select
            safe_cast(left(bss.school_year, 4) as int) as mclass_academic_year,
            bss.student_primary_id as mclass_student_number,
            'benchmark' as assessment_type,
            bss.assessment_grade as mclass_assessment_grade,
            bss.benchmark_period as mclass_period,
            bss.client_date as mclass_client_date,
            bss.sync_date as mclass_sync_date,
            u.measure as mclass_measure,
            u.score as mclass_measure_score,
            u.level as mclass_measure_level,
            u.national_norm_percentile as mclass_measure_percentile,
            u.semester_growth as mclass_measure_semester_growth,
            u.year_growth as mclass_measure_year_growth,
            null as mclass_probe_number,
            null as mclass_total_number_of_probes,
            null as mclass_score_change,
            case
                when u.level = 'Above Benchmark'
                then 4
                when u.level = 'At Benchmark'
                then 3
                when u.level = 'Below Benchmark'
                then 2
                when u.level = 'Well Below Benchmark'
                then 1
            end as mclass_measure_level_int,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        where
            cast(left(bss.school_year, 4) as int)
            >= {{ var("current_academic_year") }} - 1
        union all
        select
            safe_cast(left(school_year, 4) as int) as mclass_academic_year,
            student_primary_id as mclass_student_number,
            'pm' as assessment_type,
            cast(assessment_grade as string) as mclass_assessment_grade,
            pm_period as mclass_period,
            client_date as mclass_client_date,
            sync_date as mclass_sync_date,
            measure as mclass_measure,
            score as mclass_measure_score,
            null as mclass_measure_level,
            null as mclass_measure_percentile,
            null as mclass_measure_semester_growth,
            null as mclass_measure_year_growth,
            probe_number as mclass_probe_number,
            total_number_of_probes as mclass_total_number_of_probes,
            score_change as mclass_score_change,
            null as mclass_measure_level_int,
        from {{ ref("stg_amplify__pm_student_summary") }}
        where
            cast(left(school_year, 4) as int) >= {{ var("current_academic_year") }} - 1
    ),

    composite_only as (
        select distinct
            mclass_academic_year,
            mclass_student_number,
            mclass_period as expected_test,
            mclass_measure_level,
        from assessments_scores
        where mclass_measure = 'Composite'
    ),

    overall_composite_by_window as (
        select distinct
            mclass_academic_year, mclass_student_number, p.boy, p.moy, p.eoy,
        from
            composite_only pivot (
                max(mclass_measure_level) for expected_test in ('BOY', 'MOY', 'EOY')
            ) as p
    ),

    probe_eligible_tag as (
        select distinct
            s.mclass_academic_year,
            s.mclass_student_number,
            c.boy,
            c.moy,
            c.eoy,
            case
                when c.boy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                when c.boy is null
                then 'No data'
                else 'No'
            end as boy_probe_eligible,
            case
                when c.moy in ('Below Benchmark', 'Well Below Benchmark')
                then 'Yes'
                when c.moy is null
                then 'No data'
                else 'No'
            end as moy_probe_eligible,
        from assessments_scores as s
        left join
            overall_composite_by_window as c
            on s.mclass_academic_year = c.mclass_academic_year
            and s.mclass_student_number = c.mclass_student_number
    )

select
    s.mclass_academic_year,
    s.mclass_student_number,
    s.assessment_type,
    s.mclass_assessment_grade,
    s.mclass_period,
    s.mclass_client_date,
    s.mclass_sync_date,
    s.mclass_measure,
    s.mclass_measure_score,
    s.mclass_measure_level,
    s.mclass_measure_level_int,

    s.mclass_measure_percentile,
    s.mclass_measure_semester_growth,
    s.mclass_measure_year_growth,
    s.mclass_probe_number,
    s.mclass_total_number_of_probes,
    s.mclass_score_change,

    p.boy_probe_eligible,
    p.moy_probe_eligible,
    p.boy as boy_composite,
    p.moy as moy_composite,
    p.eoy as eoy_composite,

    case
        when p.boy_probe_eligible = 'Yes' and s.mclass_period = 'BOY->MOY'
        then p.boy_probe_eligible
        when p.moy_probe_eligible = 'Yes' and s.mclass_period = 'MOY->EOY'
        then p.moy_probe_eligible
        when p.boy_probe_eligible = 'No' and s.mclass_period = 'BOY->MOY'
        then 'No'
        when p.moy_probe_eligible = 'No' and s.mclass_period = 'MOY->EOY'
        then 'No'
        else 'Not applicable'
    end as pm_probe_eligible,

    case
        when
            p.boy_probe_eligible = 'Yes'
            and s.mclass_period = 'BOY->MOY'
            and s.mclass_total_number_of_probes is not null
        then 'Yes'
        when
            p.moy_probe_eligible = 'Yes'
            and s.mclass_period = 'MOY->EOY'
            and s.mclass_total_number_of_probes is not null
        then 'Yes'
        when
            p.boy_probe_eligible = 'Yes'
            and s.mclass_period = 'BOY->MOY'
            and s.mclass_total_number_of_probes is null
        then 'No'
        when
            p.moy_probe_eligible = 'Yes'
            and s.mclass_period = 'MOY->EOY'
            and s.mclass_total_number_of_probes is null
        then 'No'
        else 'Not applicable'
    end as pm_probe_tested,

from assessments_scores as s
left join
    probe_eligible_tag as p
    on s.mclass_academic_year = p.mclass_academic_year
    and s.mclass_student_number = p.mclass_student_number
